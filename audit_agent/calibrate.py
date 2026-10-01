"""Calibration helpers for the Solidity audit detector.

This module loads `data/synthetic_features.csv`, fits an IsolationForest model,
computes anomaly scores for the dataset, and optionally visualizes the feature
space with a scatter plot.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "synthetic_features.csv"


@dataclass
class CalibrationResult:
    model: IsolationForest
    features: np.ndarray
    scores: np.ndarray
    labels: List[str]
    filenames: List[str]


def load_dataset(path: str | Path = DATA_FILE) -> pd.DataFrame:
    """Load the synthetic dataset from CSV."""
    return pd.read_csv(path)


def fit_calibration_model(df: pd.DataFrame, random_state: int = 42) -> CalibrationResult:
    """Fit an IsolationForest on the supplied feature dataset."""
    feature_cols = [
        "loc",
        "num_functions",
        "num_modifiers",
        "num_low_level_calls",
        "num_branches",
        "num_assembly",
        "num_payable",
    ]
    features = df[feature_cols].astype(float).to_numpy()
    model = IsolationForest(random_state=random_state, contamination=0.1)
    model.fit(features)
    scores = model.decision_function(features)
    return CalibrationResult(
        model=model,
        features=features,
        scores=scores,
        labels=df["label"].astype(str).tolist(),
        filenames=df["filename"].astype(str).tolist(),
    )


def plot_calibration(result: CalibrationResult, output_path: str | Path | None = None) -> None:
    """Plot a simple pairwise feature visualization of the calibration data."""
    # Use the first two numeric features for a simple 2D scatter plot. x = LOC, y = num_functions.We're plotting contract size vs complexity.
    x = result.features[:, 0]
    y = result.features[:, 1]
    labels = result.labels

    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(x, y, c=np.where(result.scores < 0, 1, 0), cmap="coolwarm", s=80, alpha=0.8)
    for i, filename in enumerate(result.filenames):
        plt.text(x[i] + 1.0, y[i] + 0.5, filename, fontsize=8)
    plt.title("Calibration Data: LOC vs num_functions with Anomaly Score")
    plt.xlabel("LOC")
    plt.ylabel("num_functions")
    plt.colorbar(scatter, label="Anomaly indicator (red = more anomalous)")
    plt.grid(True, linestyle="--", alpha=0.4)

    if output_path is not None:
        plt.savefig(str(output_path), bbox_inches="tight")
        print(f"Saved calibration visualization to {output_path}")
    else:
        plt.show()


def calibrate_and_plot(path: str | Path | None = None, output_path: str | Path | None = None) -> CalibrationResult:
    """Load data, fit the model, and optionally plot the calibration results."""
    df = load_dataset(path or DATA_FILE)
    result = fit_calibration_model(df)
    plot_calibration(result, output_path=output_path)
    return result


# CLI execution block
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calibrate the Solidity audit detector from synthetic CSV features.")
    parser.add_argument("--data", help="Path to synthetic_features.csv", default=str(DATA_FILE))
    parser.add_argument("--output", help="Optional path to save the plot image")
    parser.add_argument("--report", action="store_true", help="Print a calibration report to stdout")
    args = parser.parse_args()

    result = calibrate_and_plot(path=args.data, output_path=args.output)
    if args.report:
        from .calibration_report import print_report

        print_report(result)
