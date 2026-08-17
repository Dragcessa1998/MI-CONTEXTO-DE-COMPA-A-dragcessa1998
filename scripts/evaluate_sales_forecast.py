"""Time-aware technical evaluation of Nexova's sales forecasting model."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

try:
    from scripts.train_sales_forecast import (
        DEFAULT_DATASET,
        build_features,
        build_model,
        load_sales_data,
        temporal_split,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/evaluate_sales_forecast.py
    from train_sales_forecast import (  # type: ignore[no-redef]
        DEFAULT_DATASET,
        build_features,
        build_model,
        load_sales_data,
        temporal_split,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "eval"
N_SPLITS = 5


def temporal_cv_splits(row_count: int, n_splits: int = N_SPLITS) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield expanding-window folds whose validation rows always follow training."""

    indices = np.arange(row_count)
    yield from TimeSeriesSplit(n_splits=n_splits).split(indices)


def _regression_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae_usd": float(mean_absolute_error(actual, predicted)),
        "rmse_usd": math.sqrt(float(mean_squared_error(actual, predicted))),
    }


def evaluate_temporal_cv(train: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run five chronological folds and retain train/validation learning points."""

    features = build_features(train)
    target = train["revenue_usd"].to_numpy(dtype=float)
    folds: list[dict[str, Any]] = []

    for fold_number, (train_idx, validation_idx) in enumerate(temporal_cv_splits(len(train)), start=1):
        if train_idx.max() >= validation_idx.min():
            raise ValueError("Temporal cross-validation leaked future rows into training.")
        model = clone(build_model())
        model.fit(features.iloc[train_idx], target[train_idx])
        train_metrics = _regression_metrics(target[train_idx], model.predict(features.iloc[train_idx]))
        validation_metrics = _regression_metrics(
            target[validation_idx], model.predict(features.iloc[validation_idx])
        )
        folds.append({
            "fold": fold_number,
            "train_rows": int(len(train_idx)),
            "validation_rows": int(len(validation_idx)),
            "train_from": train.iloc[train_idx]["month"].min().date().isoformat(),
            "train_to": train.iloc[train_idx]["month"].max().date().isoformat(),
            "validation_from": train.iloc[validation_idx]["month"].min().date().isoformat(),
            "validation_to": train.iloc[validation_idx]["month"].max().date().isoformat(),
            "train": train_metrics,
            "validation": validation_metrics,
        })

    validation_mae = np.array([fold["validation"]["mae_usd"] for fold in folds])
    validation_rmse = np.array([fold["validation"]["rmse_usd"] for fold in folds])
    train_mae = np.array([fold["train"]["mae_usd"] for fold in folds])
    train_rmse = np.array([fold["train"]["rmse_usd"] for fold in folds])
    summary = {
        "folds": N_SPLITS,
        "validation_mae_mean_usd": float(validation_mae.mean()),
        "validation_mae_std_usd": float(validation_mae.std(ddof=1)),
        "validation_rmse_mean_usd": float(validation_rmse.mean()),
        "validation_rmse_std_usd": float(validation_rmse.std(ddof=1)),
        "train_mae_mean_usd": float(train_mae.mean()),
        "train_rmse_mean_usd": float(train_rmse.mean()),
    }
    return folds, summary


def diagnose_fit(folds: list[dict[str, Any]], mean_revenue: float) -> tuple[str, str]:
    """Classify fit from the final expanding fold using explicit thresholds."""

    final_train = folds[-1]["train"]["rmse_usd"]
    final_validation = folds[-1]["validation"]["rmse_usd"]
    gap_ratio = final_validation / final_train if final_train else float("inf")
    train_relative = final_train / mean_revenue
    validation_relative = final_validation / mean_revenue

    if gap_ratio >= 1.5 and validation_relative >= 0.05:
        return (
            "overfitting",
            "Increase min_samples_leaf from 2 to 4–6, reduce max_depth from 8 to 5–6, "
            "and select those values with the same expanding-window validation; do not tune on 2024–2025.",
        )
    if train_relative >= 0.10 and validation_relative >= 0.10 and gap_ratio < 1.5:
        return (
            "underfitting",
            "Add explicit lagged revenue and rolling-trend features available at prediction time, then repeat the same temporal validation.",
        )
    return (
        "well fitted",
        "Keep the current complexity and add a monthly drift check; retrain only when temporal RMSE exceeds the documented validation band.",
    )


def render_learning_curve(folds: list[dict[str, Any]], destination: Path) -> None:
    sizes = [fold["train_rows"] for fold in folds]
    train_rmse = [fold["train"]["rmse_usd"] for fold in folds]
    validation_rmse = [fold["validation"]["rmse_usd"] for fold in folds]
    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.plot(sizes, train_rmse, marker="o", linewidth=2, label="Training RMSE")
    axis.plot(sizes, validation_rmse, marker="s", linewidth=2, label="Next-block validation RMSE")
    axis.set(
        title="Nexova sales forecast — temporal learning curve",
        xlabel="Chronological training rows",
        ylabel="RMSE (USD)",
    )
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def write_report(results: dict[str, Any], destination: Path) -> None:
    cv = results["cross_validation"]
    final_fold = results["folds"][-1]
    report = f"""# Nexova Sales Forecast — Formal Evaluation

## Decision

The model is classified as **{results['diagnosis']}**. In the final expanding fold,
training RMSE is **${final_fold['train']['rmse_usd']:,.2f}** and validation RMSE is
**${final_fold['validation']['rmse_usd']:,.2f}**. The learning curve in
`learning_curve.png` shows the evidence behind this classification.

## Time-aware stability

Five expanding-window folds preserve chronology; every validation block occurs
strictly after its training block. Validation RMSE is
**${cv['validation_rmse_mean_usd']:,.2f} ± ${cv['validation_rmse_std_usd']:,.2f}**,
and validation MAE is
**${cv['validation_mae_mean_usd']:,.2f} ± ${cv['validation_mae_std_usd']:,.2f}**.
The standard deviation is material, so a single holdout number would overstate
confidence in month-to-month stability.

## Metric choice and business cost

Both MAE and RMSE are reported for training and validation. **RMSE is primary**:
Laura Mendoza uses the forecast for capacity, hiring, and consolidated planning,
so an occasional large overestimate can commit Nexova to excess staffing and an
equally large underestimate can leave revenue opportunities understaffed. RMSE
penalizes those large misses more strongly. MAE remains the directly interpretable
typical monthly dollar error.

## Corrective action

{results['corrective_action']}

The untouched 2024–2025 test period remains outside this evaluation and must not
be used for model selection.
"""
    destination.write_text(report, encoding="utf-8")


def run_evaluation(dataset: Path = DEFAULT_DATASET, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    frame = load_sales_data(dataset)
    train, _test = temporal_split(frame)
    folds, cv_summary = evaluate_temporal_cv(train)
    diagnosis, corrective_action = diagnose_fit(folds, float(train["revenue_usd"].mean()))
    results: dict[str, Any] = {
        "dataset": str(dataset.relative_to(REPO_ROOT)) if dataset.is_relative_to(REPO_ROOT) else str(dataset),
        "diagnosis": diagnosis,
        "corrective_action": corrective_action,
        "cross_validation": cv_summary,
        "folds": folds,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "regression_evaluation_metrics.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    render_learning_curve(folds, output_dir / "learning_curve.png")
    write_report(results, output_dir / "evaluation_report.md")
    return results


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2))
