"""Train and evaluate Nexova's reproducible monthly revenue forecast."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.ticker import FuncFormatter
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

plt.switch_backend("Agg")


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "data" / "raw" / "nexova_sales.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "eval"
EXPECTED_COLUMNS = (
    "month",
    "revenue_usd",
    "active_contracts",
    "avg_contract_value_usd",
    "business_line",
)
FEATURE_COLUMNS = (
    "month_index",
    "month_sin",
    "month_cos",
    "active_contracts",
    "avg_contract_value_usd",
)
RANDOM_STATE = 42


def load_sales_data(path: Path = DEFAULT_DATASET) -> pd.DataFrame:
    """Load and validate the official 120-month Nexova consolidated dataset."""

    frame = pd.read_csv(path)
    if tuple(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            f"expected columns {EXPECTED_COLUMNS}, got {tuple(frame.columns)}"
        )

    frame["month"] = pd.to_datetime(frame["month"], format="%Y-%m-%d", errors="coerce")
    for column in ("revenue_usd", "active_contracts", "avg_contract_value_usd"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if frame.isna().any().any():
        raise ValueError("dataset contains null, empty, or invalid values")
    if set(frame["business_line"]) != {"consolidated"}:
        raise ValueError("the forecasting dataset must contain consolidated rows only")
    if frame["month"].duplicated().any():
        raise ValueError("dataset contains duplicate months")
    if (
        (frame[["revenue_usd", "active_contracts", "avg_contract_value_usd"]] <= 0)
        .any()
        .any()
    ):
        raise ValueError(
            "revenue, active contracts, and average contract value must be positive"
        )

    frame = frame.sort_values("month", kind="stable").reset_index(drop=True)
    expected_months = pd.date_range("2016-01-01", "2025-12-01", freq="MS")
    if len(frame) != len(expected_months) or not frame["month"].equals(
        pd.Series(expected_months)
    ):
        raise ValueError(
            "dataset must contain every month from 2016-01 through 2025-12"
        )
    return frame


def temporal_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the first eight years for training and the final two for testing."""

    years = sorted(int(year) for year in frame["month"].dt.year.unique())
    if len(years) != 10:
        raise ValueError("the official split requires exactly ten calendar years")
    training_years = set(years[:8])
    test_years = set(years[8:])
    train = frame[frame["month"].dt.year.isin(training_years)].copy()
    test = frame[frame["month"].dt.year.isin(test_years)].copy()
    if (
        len(train) != 96
        or len(test) != 24
        or train["month"].max() >= test["month"].min()
    ):
        raise ValueError("the 8-year/2-year chronological split is invalid")
    return train.reset_index(drop=True), test.reset_index(drop=True)


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create calendar, trend and contract features without using the target."""

    month_number = frame["month"].dt.month.astype(float)
    month_index = (
        (frame["month"].dt.year - 2016) * 12 + frame["month"].dt.month - 1
    ).astype(float)
    return pd.DataFrame(
        {
            "month_index": month_index,
            "month_sin": np.sin(2 * np.pi * month_number / 12),
            "month_cos": np.cos(2 * np.pi * month_number / 12),
            "active_contracts": frame["active_contracts"].astype(float),
            "avg_contract_value_usd": frame["avg_contract_value_usd"].astype(float),
        },
        index=frame.index,
    )


def build_model() -> Pipeline:
    """Use an explainable forest with a fixed seed and bounded tree complexity."""

    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "forest",
                RandomForestRegressor(
                    n_estimators=500,
                    max_depth=8,
                    min_samples_leaf=2,
                    max_features=0.8,
                    n_jobs=-1,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def prediction_band(
    model: Pipeline, features: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return mean prediction and P10/P90 spread across fitted forest trees."""

    scaled = model.named_steps["scale"].transform(features)
    forest: RandomForestRegressor = model.named_steps["forest"]
    tree_predictions = np.vstack([tree.predict(scaled) for tree in forest.estimators_])
    return (
        tree_predictions.mean(axis=0),
        np.percentile(tree_predictions, 10, axis=0),
        np.percentile(tree_predictions, 90, axis=0),
    )


def population_stability_index(
    expected: np.ndarray, actual: np.ndarray, bins: int = 10
) -> float:
    """Measure train-to-test distribution shift using expected quantile bins."""

    expected_values = np.asarray(expected, dtype=float)
    actual_values = np.asarray(actual, dtype=float)
    boundaries = np.unique(np.quantile(expected_values, np.linspace(0, 1, bins + 1)))
    if len(boundaries) < 3:
        return 0.0
    boundaries[0], boundaries[-1] = -np.inf, np.inf
    expected_counts, _ = np.histogram(expected_values, bins=boundaries)
    actual_counts, _ = np.histogram(actual_values, bins=boundaries)
    epsilon = 1e-6
    expected_ratio = np.clip(expected_counts / len(expected_values), epsilon, None)
    actual_ratio = np.clip(actual_counts / len(actual_values), epsilon, None)
    return float(
        np.sum((actual_ratio - expected_ratio) * np.log(actual_ratio / expected_ratio))
    )


def _gini(actual: np.ndarray, prediction: np.ndarray) -> float:
    order = np.lexsort((np.arange(len(prediction)), -prediction))
    ordered_actual = actual[order]
    cumulative = np.cumsum(ordered_actual)
    if cumulative[-1] == 0:
        return 0.0
    return float(cumulative.sum() / cumulative[-1] - (len(actual) + 1) / 2)


def normalized_gini(actual: np.ndarray, prediction: np.ndarray) -> float:
    """Return ranking quality normalized so a perfect ordering equals 1."""

    denominator = _gini(actual, actual)
    return _gini(actual, prediction) / denominator if denominator else 0.0


def calculate_metrics(
    train: pd.DataFrame,
    test: pd.DataFrame,
    predicted: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> dict[str, Any]:
    actual = test["revenue_usd"].to_numpy(dtype=float)
    mse = float(mean_squared_error(actual, predicted))
    rmse = math.sqrt(mse)
    mean_revenue = float(actual.mean())
    feature_psi = {
        column: population_stability_index(
            build_features(train)[column].to_numpy(),
            build_features(test)[column].to_numpy(),
        )
        for column in FEATURE_COLUMNS
    }
    k2 = float(r2_score(actual, predicted))
    return {
        "test_period": {
            "from": test["month"].min().date().isoformat(),
            "to": test["month"].max().date().isoformat(),
            "months": len(test),
        },
        "mse_usd_squared": mse,
        "rmse_usd": rmse,
        "rmse_percent_of_mean_revenue": rmse / mean_revenue * 100,
        "mse_percent_of_mean_revenue_squared": mse / (mean_revenue**2) * 100,
        "psi_revenue_train_vs_test": population_stability_index(
            train["revenue_usd"].to_numpy(dtype=float), actual
        ),
        "psi_by_feature": feature_psi,
        "normalized_gini": normalized_gini(actual, predicted),
        "k2_score": k2,
        "k2_definition": "Course label operationalized as R² coefficient of determination.",
        "prediction_band_coverage_percent": float(
            np.mean((actual >= lower) & (actual <= upper)) * 100
        ),
        "mean_test_revenue_usd": mean_revenue,
    }


def render_forecast_chart(
    test: pd.DataFrame,
    predicted: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    destination: Path,
) -> None:
    """Export an honest 24-month actual-vs-predicted trend with variability."""

    months = test["month"]
    actual = test["revenue_usd"].to_numpy(dtype=float)
    figure, axis = plt.subplots(figsize=(13, 7), constrained_layout=True)
    figure.patch.set_facecolor("#ffffff")
    axis.set_facecolor("#fbfcfe")
    axis.fill_between(
        months,
        lower,
        upper,
        color="#f4b183",
        alpha=0.32,
        label="Variabilidad P10–P90 entre árboles",
    )
    axis.plot(
        months,
        actual,
        color="#16324f",
        marker="o",
        markersize=4,
        linewidth=2.4,
        label="Ingreso real",
    )
    axis.plot(
        months,
        predicted,
        color="#c65f20",
        linestyle="--",
        marker="s",
        markersize=3.5,
        linewidth=2.1,
        label="Predicción Random Forest",
    )
    axis.set_title(
        "Predicción mensual de ingresos de Nexova",
        loc="left",
        fontsize=16,
        weight="bold",
        pad=38,
    )
    axis.text(
        0,
        1.015,
        "24 meses de prueba (2024–2025) · USD · banda de variabilidad del ensamble, no intervalo de confianza",
        transform=axis.transAxes,
        color="#4b5563",
        fontsize=10,
    )
    axis.set_ylabel("Ingresos consolidados (USD)")
    axis.set_xlabel("Mes")
    axis.set_xlim(months.iloc[0], months.iloc[-1])
    axis.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"${value / 1_000_000:.2f}M")
    )
    axis.grid(axis="y", color="#d8dee8", linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.tick_params(colors="#374151")
    axis.legend(loc="upper right", frameon=False, ncol=1)
    axis.text(
        0,
        -0.16,
        "Fuente: data/raw/nexova_sales.csv (dataset oficial del contexto). Semilla fija: 42.",
        transform=axis.transAxes,
        color="#6b7280",
        fontsize=9,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


def write_report(metrics: dict[str, Any], destination: Path) -> None:
    """Write the business-readable evaluation required by the RFI."""

    psi = metrics["psi_revenue_train_vs_test"]
    psi_note = (
        "cambio material de distribución"
        if psi >= 0.25
        else "cambio moderado de distribución"
        if psi >= 0.1
        else "distribución estable"
    )
    report = f"""# Nexova Sales Forecast — Technical Summary

## Decision

Random Forest is the selected baseline because Laura and Finance need an
explainable feasibility model on only 96 training observations. It offers
feature importance and a transparent spread across its trees without the extra
tuning surface of XGBoost. The fixed seed makes the experiment reproducible.

## Test design

- Official dataset: 120 monthly consolidated rows, 2016-01 through 2025-12.
- Train: first 8 years (96 rows, 2016-01 through 2023-12).
- Test: final 2 years (24 unseen rows, 2024-01 through 2025-12).
- Features: calendar trend/seasonality, active contracts and average contract
  value. The target `revenue_usd` is never used as an input feature.

## Test metrics

| Metric | Result | Interpretation |
| --- | ---: | --- |
| MSE | {metrics["mse_usd_squared"]:,.2f} USD² | Penalizes large misses quadratically. |
| MSE / mean revenue² | {metrics["mse_percent_of_mean_revenue_squared"]:.2f}% | Dimensionless normalization of the squared error. |
| RMSE | {metrics["rmse_usd"]:,.2f} USD | Typical error in Finance-readable units. |
| RMSE / mean revenue | {metrics["rmse_percent_of_mean_revenue"]:.2f}% | Scale-aware error against average test revenue. |
| PSI (revenue, train vs test) | {psi:.4f} | {psi_note.capitalize()}. |
| Normalized Gini | {metrics["normalized_gini"]:.4f} | Ability to rank weak vs strong months. |
| K2 score | {metrics["k2_score"]:.4f} | Course label mapped explicitly to regression R². |
| P10–P90 band coverage | {metrics["prediction_band_coverage_percent"]:.1f}% | Descriptive tree spread, not a calibrated confidence interval. |

MSE alone is not sufficient: its squared units are difficult to budget against,
it does not reveal ranking quality, and it hides train-to-test distribution
shift. RMSE is therefore the primary Finance metric; Gini answers Laura's need
to distinguish August slowdowns from stronger January/February months, while
PSI warns that the recent period differs from the training population.

For future inference, Finance must provide planned `active_contracts` and
`avg_contract_value_usd`; they are contemporaneous operational inputs, not
values forecast by this model. The calendar-only alternative would avoid that
dependency but would be materially less useful with a 120-row dataset.

`K2 score` is not a standard regression metric in scikit-learn. To keep the
course contract auditable, this implementation reports that label as R² (the
coefficient of determination) and stores the definition next to the value. See
the [official regression metric reference](https://scikit-learn.org/stable/api/sklearn.metrics.html#regression-metrics).

## Visualization

![Actual revenue, prediction and P10–P90 ensemble variability](sales_forecast_test_period.png)

The band is the 10th–90th percentile across individual forest trees. It shows
model variability, but must not be presented as a calibrated probability or
confidence interval.
"""
    destination.write_text(report, encoding="utf-8")


def run(
    dataset: Path = DEFAULT_DATASET, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> dict[str, Any]:
    frame = load_sales_data(dataset)
    train, test = temporal_split(frame)
    model = build_model()
    model.fit(build_features(train), train["revenue_usd"])
    predicted, lower, upper = prediction_band(model, build_features(test))
    metrics = calculate_metrics(train, test, predicted, lower, upper)

    output_dir.mkdir(parents=True, exist_ok=True)
    predictions = pd.DataFrame(
        {
            "month": test["month"].dt.strftime("%Y-%m-%d"),
            "actual_revenue_usd": test["revenue_usd"],
            "predicted_revenue_usd": np.round(predicted, 2),
            "prediction_p10_usd": np.round(lower, 2),
            "prediction_p90_usd": np.round(upper, 2),
        }
    )
    predictions.to_csv(output_dir / "sales_forecast_predictions.csv", index=False)
    (output_dir / "sales_forecast_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    joblib.dump(model, output_dir / "nexova_sales_random_forest.joblib")
    render_forecast_chart(
        test,
        predicted,
        lower,
        upper,
        output_dir / "sales_forecast_test_period.png",
    )
    write_report(metrics, output_dir / "sales_forecast_report.md")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train Nexova's monthly sales forecast"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args()
    metrics = run(arguments.dataset, arguments.output_dir)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
