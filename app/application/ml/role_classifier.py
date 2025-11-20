# app/application/ml/role_classifier.py
import pickle, numpy as np, pandas as pd
from typing import Tuple, Optional
from .features import column_features

ROLE_LABELS = ["fecha","métrica_monetaria","métrica_numérica","categórica","bool","id","geo","texto"]

class RoleClassifier:
    def __init__(self, path="models/role_clf.pkl"):
        self.model = None
        try:
            with open(path, "rb") as f:
                self.model = pickle.load(f)
        except Exception:
            self.model = None

    def available(self) -> bool:
        return self.model is not None

    def predict(self, name: str, series: pd.Series) -> Tuple[Optional[str], float]:
        f = column_features(name, series)
        if not self.model:
            return None, 0.0
        X = np.array([[f[k] for k in self.model.feature_names_in_]])
        proba = self.model.predict_proba(X)[0]
        idx = int(np.argmax(proba))
        return ROLE_LABELS[idx], float(proba[idx])
