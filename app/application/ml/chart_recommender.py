# app/application/ml/chart_recommender.py
import pickle
from typing import Dict, Any, List
from .features import role_hist_features

CHART_TYPES = ["line_time","bar_top","hist","pie","heatmap","scatter"]

class ChartRecommender:
    def __init__(self, path="models/chart_rec.pkl"):
        self.model = None
        try:
            with open(path,"rb") as f:
                self.model = pickle.load(f)
        except Exception:
            self.model = None

    def available(self) -> bool:
        return self.model is not None

    def recommend_types(self, schema) -> List[str]:
        # Si no hay modelo → reglas mínimas
        if not self.model:
            out = []
            if schema.primary_date and schema.primary_metric: out.append("line_time")
            out.append("bar_top")
            if not schema.primary_metric: out.append("hist")
            return out[:4]
        # Features simples por ahora: conteos de roles + flags
        feats = role_hist_features(schema.roles)
        feats["has_primary_date"] = int(bool(schema.primary_date))
        feats["has_metric"] = int(bool(schema.primary_metric))
        import numpy as np
        X = np.array([[feats.get(k,0) for k in self.model.feature_names_in_]])
        probs = self.model.predict_proba(X)[0]  # multi-class top-k
        ranked = [t for _,t in sorted(zip(probs, CHART_TYPES), reverse=True)]
        return ranked[:4]
