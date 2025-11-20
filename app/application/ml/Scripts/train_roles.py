# scripts/train_roles.py
import os, glob, pickle
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from app.application.ml.features import column_features
from app.application.semantics import infer_semantics  # usa tus heurísticas actuales como weak labels

ROLE_LABELS = ["fecha","métrica_monetaria","métrica_numérica","categórica","bool","id","geo","texto"]

def gather_columns(paths):
    rows = []
    for p in paths:
        df = pd.read_excel(p) if p.lower().endswith((".xlsx",".xls")) else pd.read_csv(p)
        schema = infer_semantics(df)  # heurísticas → roles débiles
        for c in df.columns:
            role = schema.roles.get(c, "categórica")
            f = column_features(c, df[c])
            rows.append((f, ROLE_LABELS.index(role) if role in ROLE_LABELS else ROLE_LABELS.index("categórica")))
    X = pd.DataFrame([r[0] for r in rows])
    y = np.array([r[1] for r in rows])
    return X, y

def main():
    os.makedirs("models", exist_ok=True)
    paths = glob.glob("data/training/columns/**/*.*", recursive=True)
    if not paths:
        print("No hay archivos en data/training/columns/. Agrega planillas para bootstrap.")
        return
    X, y = gather_columns(paths)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=400, random_state=42, class_weight="balanced")
    clf.fit(X_train, y_train)
    acc = clf.score(X_val, y_val)
    print("Val acc:", acc)
    with open("models/role_clf.pkl","wb") as f:
        pickle.dump(clf, f)
    print("Guardado: models/role_clf.pkl")

if __name__ == "__main__":
    main()
