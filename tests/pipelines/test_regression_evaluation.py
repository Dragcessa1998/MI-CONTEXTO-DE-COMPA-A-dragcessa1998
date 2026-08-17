"""Temporal integrity tests for the formal regression evaluation."""

from pathlib import Path

from scripts.evaluate_sales_forecast import N_SPLITS, run_evaluation, temporal_cv_splits
from scripts.train_sales_forecast import load_sales_data, temporal_split


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "data" / "raw" / "nexova_sales.csv"


def test_every_temporal_fold_trains_strictly_before_validation() -> None:
    train, _test = temporal_split(load_sales_data(DATASET))
    folds = list(temporal_cv_splits(len(train)))
    assert len(folds) == N_SPLITS
    previous_validation_end = -1
    for train_indices, validation_indices in folds:
        assert list(train_indices) == sorted(train_indices)
        assert list(validation_indices) == sorted(validation_indices)
        assert train_indices.max() < validation_indices.min()
        assert previous_validation_end < validation_indices.min()
        previous_validation_end = int(validation_indices.max())


def test_evaluation_writes_required_artifacts(tmp_path: Path) -> None:
    results = run_evaluation(DATASET, tmp_path)
    assert results["diagnosis"] in {"well fitted", "underfitting", "overfitting"}
    assert results["cross_validation"]["folds"] == 5
    assert results["cross_validation"]["validation_rmse_mean_usd"] > 0
    assert (tmp_path / "learning_curve.png").stat().st_size > 0
    assert (tmp_path / "evaluation_report.md").is_file()
    assert (tmp_path / "regression_evaluation_metrics.json").is_file()
