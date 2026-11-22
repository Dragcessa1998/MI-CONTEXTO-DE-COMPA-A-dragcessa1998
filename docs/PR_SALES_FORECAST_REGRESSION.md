## Summary

Completes **Sales Forecasting with a Regression Model** using Nexova's official
2016–2025 monthly consolidated revenue dataset.

- validates the exact dataset contract, positive values and complete 120-month sequence;
- preserves the required chronological split: 2016–2023 train, 2024–2025 test;
- trains an explainable Random Forest with `random_state=42` on causal features:
  revenue lags 1/2/12 and 3/12-month rolling means (`shift(1)` before `rolling`),
  plus `active_contracts` and `avg_contract_value_usd` lagged one month. Same-month
  contracts x average value (almost the target, unknown in advance) is no longer used;
  the 12 warm-up months of 2016 without full history are dropped from training;
- reports test MSE, PSI, normalized Gini and the requested K2 score (explicitly
  defined as regression R²), plus Finance-readable RMSE;
- exports the trained model, exact predictions and a P10–P90 per-tree
  variability chart;
- adds tests covering the dataset, 8/2 split, feature boundary, invalid input and a
  no-leakage test (perturbing month t and later never changes features up to t).

Random Forest was selected over XGBoost because only 84 usable monthly training rows
are available, Finance values explainability, and the ensemble exposes a useful
descriptive variability range without another tuned dependency.

## Results on the unseen 2024–2025 test period (one-step-ahead)

| Metric | Before (same-month contracts, leaky) | Now (causal lags) |
| --- | ---: | ---: |
| MSE | 3,595,945,525.65 USD² | 3,164,183,646.24 USD² |
| RMSE | 59,966.20 USD (6.25%) | 56,251.08 USD (5.86%) |
| Revenue PSI | 8.1602 | 8.1274 |
| Normalized Gini | 0.8939 | 0.8132 |
| K2/R² | 0.5179 | 0.5758 |
| P10–P90 coverage | 58.3% | 79.2% |

Revenue PSI changes only because the 2016 warm-up rows leave the train sample.
Without the leaky inputs, error and R² improve slightly while ranking (Gini)
drops; the high PSI and moderate R² still mean this is a feasibility baseline,
not a staging-ready forecast. Inference now needs only already-closed months.

## Validation

- `uv run pytest tests/pipelines/test_sales_forecast.py -q` — **6 passed**
- `uv run python -m scripts.train_sales_forecast` — exits 0 and regenerates all artifacts
- `git diff --check` — clean
