"""Generate a simple calibration report for the audit detector."""

from dataclasses import dataclass # importing the @dataclass decorator.
from typing import List

import numpy as np


@dataclass
class CalibrationSummary:
    n_samples: int
    mean_score: float
    std_score: float
    anomalies: int
    labels: List[str]
    filenames: List[str]


def summarize_calibration(scores: np.ndarray, labels: List[str], filenames: List[str]) -> CalibrationSummary:
    """Summarize the calibration scores and label distribution."""
    scores = np.asarray(scores, dtype=float)
    anomalies = int(np.sum(scores < 0.0))
    return CalibrationSummary(
        n_samples=len(scores),
        mean_score=float(np.mean(scores)),
        std_score=float(np.std(scores)),
        anomalies=anomalies,
        labels=labels,
        filenames=filenames,
    )


def print_report(result) -> None:
    """Print a calibration report to stdout."""
    summary = summarize_calibration(result.scores, result.labels, result.filenames)
    print("Calibration Report")
    print("------------------")
    print(f"Samples: {summary.n_samples}")
    print(f"Mean decision score: {summary.mean_score:.4f}")
    print(f"Std deviation: {summary.std_score:.4f}")
    print(f"Anomaly count (score < 0): {summary.anomalies}")
    print("\nSample labels and filenames:")
    for filename, label in zip(summary.filenames, summary.labels):
        print(f" - {filename}: {label}")
