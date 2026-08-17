# Nexova Sales Forecast — Formal Evaluation

## Decision

The model is classified as **overfitting**. In the final expanding fold,
training RMSE is **$13,043.01** and validation RMSE is
**$44,533.49**. The learning curve in
`learning_curve.png` shows the evidence behind this classification.

## Time-aware stability

Five expanding-window folds preserve chronology; every validation block occurs
strictly after its training block. Validation RMSE is
**$47,753.47 ± $8,205.74**,
and validation MAE is
**$37,733.87 ± $6,042.93**.
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

Increase min_samples_leaf from 2 to 4–6, reduce max_depth from 8 to 5–6, and select those values with the same expanding-window validation; do not tune on 2024–2025.

The untouched 2024–2025 test period remains outside this evaluation and must not
be used for model selection.
