"""
Evaluation metrics and simple heuristic baselines for temperature regression and heat-wave classification.

Baseline Models:
1. Persistence Baseline: tomorrow's Tmax ≈ today's Tmax (lag 1)
2. YoY Baseline: predicted Tmax ≈ same date 1 year ago (T - 365)
3. Seasonal Normal Baseline: predicted Tmax ≈ smoothed climatological normal
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


@dataclass
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float
    mape: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "MAE": round(self.mae, 3),
            "RMSE": round(self.rmse, 3),
            "R2": round(self.r2, 4),
            "MAPE": round(self.mape, 2),
        }


@dataclass
class ClassificationMetrics:
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    false_positives: int
    false_negatives: int
    total_positives: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "Precision": round(self.precision, 4),
            "Recall": round(self.recall, 4),
            "F1": round(self.f1, 4),
            "ROC_AUC": round(self.roc_auc, 4),
            "PR_AUC": round(self.pr_auc, 4),
            "FP": self.false_positives,
            "FN": self.false_negatives,
            "Total_Pos": self.total_positives,
        }


def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> RegressionMetrics:
    """Calculate MAE, RMSE, R2, MAPE."""
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    yt, yp = y_true[mask], y_pred[mask]

    mae = float(mean_absolute_error(yt, yp))
    rmse = float(np.sqrt(mean_squared_error(yt, yp)))
    r2 = float(r2_score(yt, yp))
    mape = float(np.mean(np.abs((yt - yp) / np.maximum(yt, 1e-5))) * 100.0)

    return RegressionMetrics(mae=mae, rmse=rmse, r2=r2, mape=mape)


def evaluate_classification(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
) -> ClassificationMetrics:
    """Calculate Precision, Recall, F1, ROC-AUC, PR-AUC, False Negatives."""
    mask = ~np.isnan(y_true) & ~np.isnan(y_prob)
    yt = y_true[mask].astype(int)
    yp = y_prob[mask]

    y_pred = (yp >= threshold).astype(int)

    prec = float(precision_score(yt, y_pred, zero_division=0))
    rec = float(recall_score(yt, y_pred, zero_division=0))
    f1 = float(f1_score(yt, y_pred, zero_division=0))

    try:
        roc_auc = float(roc_auc_score(yt, yp)) if len(np.unique(yt)) > 1 else 0.5
    except Exception:
        roc_auc = 0.5

    try:
        pr_auc = float(average_precision_score(yt, yp)) if len(np.unique(yt)) > 1 else 0.0
    except Exception:
        pr_auc = 0.0

    cm = confusion_matrix(yt, y_pred, labels=[0, 1])
    # cm: [[TN, FP], [FN, TP]]
    fp = int(cm[0, 1]) if cm.shape == (2, 2) else 0
    fn = int(cm[1, 0]) if cm.shape == (2, 2) else 0
    total_pos = int(np.sum(yt == 1))

    return ClassificationMetrics(
        precision=prec,
        recall=rec,
        f1=f1,
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        false_positives=fp,
        false_negatives=fn,
        total_positives=total_pos,
    )
