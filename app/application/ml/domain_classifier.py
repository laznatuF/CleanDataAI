# app/application/ml/domain_classifier.py
import pickle
from typing import Dict, Any, List
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from .features import dataset_header_text, role_hist_features

DOMAINS = ["sales","hr","inventory","finance","generic"]

class DomainClassifier:
    def __init__(self, path="models/domain_clf.pkl"):
        self.pipe = None
        try:
            with open(path,"rb") as f:
                self.pipe = pickle.load(f)
        except Exception:
            self.pipe = None

    def available(self) -> bool:
        return self.pipe is not None

    def predict(self, columns: List[str], roles: Dict[str,str]) -> str:
        if not self.pipe:
            return "generic"
        text = dataset_header_text(columns)
        extras = role_hist_features(roles)
        # La pipeline que entrenamos concatena TF-IDF(text) + extras (via FeatureUnion o ColumnTransformer)
        # Para simplificar, guardamos extras en la forma "role_count_*:N" dentro del texto.
        feats_text = text + " " + " ".join([f"{k}:{v}" for k,v in extras.items()])
        return self.pipe.predict([feats_text])[0]
