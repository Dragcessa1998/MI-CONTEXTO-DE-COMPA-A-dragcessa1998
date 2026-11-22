"""Acceptance coverage for Nexova's chronological sales forecast."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.train_sales_forecast import (
    EXPECTED_COLUMNS,
    FEATURE_COLUMNS,
    FORBIDDEN_SAME_MONTH_COLUMNS,
    WARMUP_MONTHS,
    build_features,
    supervised_split,
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
    assert features.iloc[WARMUP_MONTHS:].isna().sum().sum() == 0
    assert features.iloc[:WARMUP_MONTHS].isna().any(axis=1).all()


def test_no_leakage_features_at_t_only_depend_on_data_up_to_t_minus_1() -> None:
    frame = load_sales_data(DATASET)
    baseline = build_features(frame)

    assert tuple(baseline.columns) == FEATURE_COLUMNS
    assert not set(FORBIDDEN_SAME_MONTH_COLUMNS) & set(baseline.columns)

    for t in (WARMUP_MONTHS, 50, 96, len(frame) - 1):
        perturbed = frame.copy()
        for column in ("revenue_usd", *FORBIDDEN_SAME_MONTH_COLUMNS):
            perturbed.loc[t:, column] = perturbed.loc[t:, column] * 7 + 1e6
        changed = build_features(perturbed)
        pd.testing.assert_frame_equal(changed.iloc[: t + 1], baseline.iloc[: t + 1])
        if t + 1 < len(frame):
            assert not changed.iloc[t + 1].equals(baseline.iloc[t + 1])


def test_supervised_split_keeps_8_plus_2_years_and_drops_warmup() -> None:
    train, train_x, test, test_x = supervised_split(load_sales_data(DATASET))

    assert train["month"].min() == pd.Timestamp("2017-01-01")
    assert train["month"].max() == pd.Timestamp("2023-12-01")
    assert len(train) == len(train_x) == 96 - WARMUP_MONTHS
    assert len(test) == len(test_x) == 24
    assert train_x.notna().all().all() and test_x.notna().all().all()


def test_invalid_dataset_is_rejected_before_training(tmp_path: Path) -> None:
    invalid = pd.read_csv(DATASET).drop(index=0)
    invalid_path = tmp_path / "invalid.csv"
    invalid.to_csv(invalid_path, index=False)

    with pytest.raises(ValueError, match="every month"):
        load_sales_data(invalid_path)
