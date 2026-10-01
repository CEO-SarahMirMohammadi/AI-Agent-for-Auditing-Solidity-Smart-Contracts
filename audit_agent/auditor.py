"""Static analysis and simple ML-based anomaly detection for Solidity contracts.

This module provides:
- `run_static_checks(source)` — lightweight regex/static checks that look for common
  Solidity anti-patterns (reentrancy, use of `tx.origin`, low-level calls, etc.).
- `extract_features(source)` — numeric features extracted from source used by the ML model.
- `fit_detector()` — creates a small synthetic training set and fits an IsolationForest.
- `score_contract(source)` — runs static checks, feature extraction and returns an
  anomaly score and flagged snippets.

The ML portion is intentionally small and unsupervised (IsolationForest) so there is
no large training dataset requirement — it provides heuristic anomaly scores only.
"""
from typing import List, Dict, Any
import re
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def _strip_comments(source: str) -> str:
    """Strip block and line comments from Solidity source.

    This helps avoid static findings on non-code comments such as explanatory
    text or inline notes.
    """
    without_block = re.sub(r"/\*.*?\*/", "", source, flags=re.S) #/* this is a comment in solidity */
    without_line = re.sub(r"//.*$", "", without_block, flags=re.MULTILINE) #// this is a comment in solidity
    return without_line


def run_static_checks(source: str) -> List[Dict[str, Any]]:
    """Run lightweight regex-based static checks and return findings.

    Each finding is a dict with keys: `type`, `line`, `snippet`, `detail`.
    The checks are intentionally simple and designed as quick heuristics to
    flag lines for deeper manual or LLM review.
    """
    findings = []
    original_lines = source.splitlines() # shows real code to user
    cleaned_source = _strip_comments(source) # avoid matching inside comments
    cleaned_lines = cleaned_source.splitlines()

    # A Tuple of (regex pattern, detail message) for common Solidity anti-patterns.
    patterns = [
        (r"\btx\.origin\b", "Use of tx.origin (unsafe for auth)."),
        (r"\.call\(|\.callvalue\(|\.delegatecall\(|\.transfer\(|\.send\(|selfdestruct|suicide",
         "Low-level or dangerous ether transfer or delegatecall detected."),
        (r"\bassembly\b", "Inline assembly present — inspect carefully."),
        (r"\bfor\s*\(|\bwhile\s*\(", "Loop detected — check gas usage and unbounded loops."),
        (r"\.balance\b", "Balance access detected — verify checks-effects-interactions."),
    ]

    # Check each line against the patterns and collect findings with original snippets.
    for i, (orig_line, clean_line) in enumerate(zip(original_lines, cleaned_lines), start=1):
        snippet = clean_line.strip()
        if not snippet:
            continue

        for pat, detail in patterns:
            if re.search(pat, snippet, flags=re.IGNORECASE):
                findings.append({
                    "type": "pattern",
                    "line": i,
                    "snippet": orig_line.strip(),
                    "detail": detail,
                })
                break

    # Function visibility checks (public vs external vs private)
    funcs = re.finditer(r"function\s+([a-zA-Z0-9_]+)?\s*\([^)]*\)\s*(public|external|internal|private)?",
                        cleaned_source)
    for m in funcs:
        name = m.group(1) or "<anonymous>"
        vis = (m.group(2) or "").strip()
        if vis.lower() == "public":
            findings.append({
                "type": "visibility",
                "line": cleaned_source[:m.start()].count("\n") + 1,
                "snippet": f"function {name} ... {vis}",
                "detail": "Public function — ensure intended visibility and access control.",
            })

    return findings


def extract_features(source: str) -> np.ndarray:
    """Extract simple numeric features from Solidity source for the detector.

    Returns a 1D numpy array of features in this order:
    [LOC, num_functions, num_modifiers, num_low_level_calls, num_branches, num_assembly, num_payable]
    """
    loc = len([l for l in source.splitlines() if l.strip()])
    num_functions = len(re.findall(r"\bfunction\b", source))
    num_modifiers = len(re.findall(r"\bmodifier\b", source))
    num_low_level_calls = len(re.findall(r"\.call\(|\.delegatecall\(|\.transfer\(|\.send\(|selfdestruct|suicide",
                                        source))
    num_branches = len(re.findall(r"\bif\b|\belse\b|\bswitch\b|\bcase\b", source))
    num_assembly = len(re.findall(r"\bassembly\b", source))
    num_payable = len(re.findall(r"\bpayable\b", source))

    return np.array([loc, num_functions, num_modifiers, num_low_level_calls,
                     num_branches, num_assembly, num_payable], dtype=float)


def fit_detector(random_state: int = 42) -> IsolationForest:
    """Fit a small IsolationForest on synthetic contract feature vectors.

    Synthetic sampling avoids needing a large labeled dataset; the detector
    is meant to provide heuristic anomaly signals for review, not definitive
    vulnerability classification.
    """
    rng = np.random.RandomState(random_state)
    # features: LOC, functions, modifiers, low_level_calls, branches, assembly, payable
    base = np.array([50, 5, 1, 0, 5, 0, 0], dtype=float)
    samples = base + rng.normal(scale=[30, 3, 1, 1, 3, 0.5, 0.5], size=(200, 7))
    # omit negative values
    samples = np.clip(samples, a_min=0, a_max=None)

    iso = IsolationForest(random_state=random_state, contamination=0.1)
    iso.fit(samples)
    return iso


def fit_detector_from_csv(csv_path: str, random_state: int = 42) -> IsolationForest:
    """Fit an IsolationForest on features loaded from a CSV file."""
    feature_cols = [
        "loc",
        "num_functions",
        "num_modifiers",
        "num_low_level_calls",
        "num_branches",
        "num_assembly",
        "num_payable",
    ]
    df = pd.read_csv(csv_path)
    features = df[feature_cols].astype(float).to_numpy()
    features = np.clip(features, a_min=0, a_max=None)

    iso = IsolationForest(random_state=random_state, contamination=0.1)
    iso.fit(features)
    return iso


def set_detector(detector: IsolationForest) -> None:
    """Replace the current global detector with a custom fitted model."""
    global _DET
    _DET = detector


_DET = None


def _get_detector():
    global _DET
    if _DET is None:
        _DET = fit_detector()
    return _DET


def score_contract(source: str) -> Dict[str, Any]:
    """Score a contract: run static checks, compute features, and return anomaly info.

    Returns a dict with keys: `findings`, `features`, `anomaly_score`, `is_anomaly`.
    """
    findings = run_static_checks(source)
    features = extract_features(source)
    det = _get_detector()
    score = det.decision_function(features.reshape(1, -1))[0]
    # decision_function higher -> more normal; lower -> more anomalous
    is_anomaly = score < 0.0

    return {
        "findings": findings,
        "features": features.tolist(),
        "anomaly_score": float(score),
        "is_anomaly": bool(is_anomaly),
    }
