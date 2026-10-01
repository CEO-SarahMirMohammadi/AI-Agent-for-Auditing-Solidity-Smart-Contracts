"""
Command-line interface for the Solidity auditing agent.

Usage:
python -m audit_agent.cli path/to/contract.sol
"""

import argparse
import os
from typing import List

from rich.console import Console
from rich.table import Table

from .auditor import (
    fit_detector_from_csv,
    run_static_checks,
    score_contract,
    set_detector,
)

from .llm_client import generate_review


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _select_top_snippets(findings, top_n=5) -> List[str]:
    seen = set()
    out = []

    for f in findings:
        s = f.get("snippet")

        if s and s not in seen:
            seen.add(s)
            out.append(s)

        if len(out) >= top_n:
            break

    return out


def main():
    parser = argparse.ArgumentParser(
        description="Audit a Solidity contract using static checks, ML scoring and LLM explanations."
    )

    parser.add_argument(
        "contract",
        help="Path to Solidity contract"
    )

    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of snippets to send to LLM"
    )

    parser.add_argument(
        "--retrain",
        metavar="CSV",
        help="Retrain ML detector from CSV"
    )

    parser.add_argument(
        "--groq-key",
        help="Optional Groq API key"
    )

    parser.add_argument(
        "--groq-url",
        help="Optional Groq API base URL"
    )

    args = parser.parse_args()

    console = Console()

    if not os.path.exists(args.contract):
        console.print(
            f"File not found: {args.contract}",
            style="bold red"
        )
        return

    src = _read_file(args.contract)

    console.print(
        "Running static checks...",
        style="bold"
    )

    findings = run_static_checks(src)

    console.print(
        f"Found {len(findings)} static findings."
    )

    if args.retrain:
        console.print(
            f"Retraining detector from {args.retrain}...",
            style="bold yellow"
        )

        detector = fit_detector_from_csv(args.retrain)
        set_detector(detector)

    if args.groq_key:
        os.environ["GROQ_API_KEY"] = args.groq_key
    if args.groq_url:
        os.environ["GROQ_API_URL"] = args.groq_url

    console.print(
        "Scoring with ML detector...",
        style="bold"
    )

    score = score_contract(src)

    console.print(
        f"Anomaly score: {score['anomaly_score']:.4f}"
    )

    console.print(
        f"Anomalous: {score['is_anomaly']}"
    )

    if findings:
        table = Table(title="Static Findings")

        table.add_column("Line")
        table.add_column("Type")
        table.add_column("Detail")
        table.add_column("Snippet")

        for f in findings[:50]:
            table.add_row(
                str(f.get("line", "?")),
                f.get("type", ""),
                f.get("detail", ""),
                f.get("snippet", ""),
            )

        console.print(table)

    snippets = _select_top_snippets(
        score["findings"],
        top_n=args.top
    )

    if snippets:
        console.print(
            f"Sending {len(snippets)} snippets to LLM...",
            style="bold green"
        )

        review = generate_review(snippets)

        console.rule("LLM Review")

        console.print(review)

    else:
        console.print(
            "No suspicious snippets found."
        )


if __name__ == "__main__":
    main()