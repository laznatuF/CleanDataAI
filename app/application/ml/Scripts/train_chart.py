# scripts/train_charts.py
import os, glob, pickle, numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from app.application.semantics import infer_semantics
from app.application.ml.features import role_hist_features

CHART_TYPES = ["line_time","bar_top","hist","pie","heatmap","scatter"]

def weak_label(schema) -> str:
    # Etiqueta simple (top-1) con reglas: luego el modelo generaliza
    if schema.primary_date and schema.primary_metric:
        return "line_time"
    if schema.primary_metric and schema.dims:
        return "bar_top"
    if not schema.primary_metric:
        return "hist"
    return "bar_top"

def build_dataset(paths):
    rows = []
    for p in paths:
        df = pd.read_excel(p) if p.endswith((".xlsx",".xls")) else pd.read_csv(p)
        schema = infer_semantics(df)
        y = CHART_TYPES.index(weak_label(schema))
        feats = role_hist_features(schema.roles)
        feats["has_primary_date"] = int(bool(schema.primary_date))
        feats["has_metric"] = int(bool(schema.primary_metric))
        rows.append((feats, y))
    X = pd.DataFrame([r[0] for r in rows]).fillna(0)
    y = np.array([r[1] for r in rows])
    return X, y

def main():
    os.makedirs("models", exist_ok=True)
    paths = glob.glob("data/training/datasets/**/*.*", recursive=True)
    if not paths:
        print("Agrega datasets en data/training/datasets/")
        return
    X, y = build_dataset(paths)
    clf = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
    clf.fit(X, y)
    with open("models/chart_rec.pkl","wb") as f:
        pickle.dump(clf, f)
    print("Guardado: models/chart_rec.pkl")

if __name__ == "__main__":
    main()
