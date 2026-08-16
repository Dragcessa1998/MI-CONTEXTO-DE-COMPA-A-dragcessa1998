## Summary

Completes **Sales Forecasting with a Regression Model** using Nexova's official
2016–2025 monthly consolidated revenue dataset.

- validates the exact dataset contract, positive values and complete 120-month sequence;
- preserves the required chronological split: 2016–2023 train, 2024–2025 test;
- trains an explainable Random Forest with `random_state=42` and no target leakage;
- reports test MSE, PSI, normalized Gini and the requested K2 score (explicitly
  defined as regression R²), plus Finance-readable RMSE;
- exports the trained model, exact predictions and a P10–P90 per-tree
  variability chart;
- adds four tests covering the dataset, 8/2 split, feature boundary and invalid input.

Random Forest was selected over XGBoost because only 96 monthly training rows
are available, Finance values explainability, and the ensemble exposes a useful
descriptive variability range without another tuned dependency.

## Results on the unseen 2024–2025 test period

- MSE: **3,595,945,525.65 USD²**
- RMSE: **59,966.20 USD** (**6.25%** of mean monthly test revenue)
- revenue PSI: **8.1602** (material train/test distribution shift)
- normalized Gini: **0.8939**
- K2/R²: **0.5179**
- P10–P90 tree-spread coverage: **58.3%**

The model ranks strong and weak months well, but the high PSI and moderate R²
mean this is a feasibility baseline, not yet a staging-ready forecast. Future
inference also requires planned active-contract and average-contract-value
inputs; this dependency is documented instead of hidden.

## Validation

- `uv run pytest -q` — **4 passed**
- `uv run python scripts/train_sales_forecast.py` — exits 0 and regenerates all artifacts
- official source CSV comparison — values identical (only line endings normalized)
- chart inspected at original resolution — labels, legend, uncertainty note and source fit
- `git diff --check` — clean
