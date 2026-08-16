"""Acceptance coverage for Nexova's chronological sales forecast."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.train_sales_forecast import (
    EXPECTED_COLUMNS,
    build_features,
    load_sales_data,
    temporal_split,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "data" / "raw" / "nexova_sales.csv"


def test_official_dataset_has_exact_contract_and_no_missing_months() -> None:
    frame = load_sales_data(DATASET)

    assert tuple(frame.columns) == EXPECTED_COLUMNS
    assert len(frame) == 120
    assert frame["month"].tolist() == list(
        pd.date_range("2016-01-01", "2025-12-01", freq="MS")
    )
    assert frame.isna().sum().sum() == 0
    assert (frame["revenue_usd"] > 0).all()


def test_temporal_split_is_exactly_eight_years_then_two_without_leakage() -> None:
    train, test = temporal_split(load_sales_data(DATASET))

    assert len(train) == 8 * 12
    assert len(test) == 2 * 12
    assert train["month"].min() == pd.Timestamp("2016-01-01")
    assert train["month"].max() == pd.Timestamp("2023-12-01")
    assert test["month"].min() == pd.Timestamp("2024-01-01")
    assert test["month"].max() == pd.Timestamp("2025-12-01")
    assert train["month"].max() < test["month"].min()
    assert set(train["month"]).isdisjoint(set(test["month"]))


def test_model_features_never_include_revenue_target() -> None:
    features = build_features(load_sales_data(DATASET))

    assert "revenue_usd" not in features.columns
    assert features.isna().sum().sum() == 0


def test_invalid_dataset_is_rejected_before_training(tmp_path: Path) -> None:
    invalid = pd.read_csv(DATASET).drop(index=0)
    invalid_path = tmp_path / "invalid.csv"
    invalid.to_csv(invalid_path, index=False)

    with pytest.raises(ValueError, match="every month"):
        load_sales_data(invalid_path)
