# scripts/train_domain.py
import os, glob, pickle
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from app.application.semantics import infer_semantics
from app.application.ml.features import dataset_header_text, role_hist_features

def load_labeled():
    # Espera archivos en data/training/datasets/ con nombre {domain}__*.csv|xlsx
    items = []
    for p in glob.glob("data/training/datasets/**/*.*", recursive=True):
        name = os.path.basename(p).lower()
        if "__" not in name: 
            continue
        domain = name.split("__",1)[0]
        df = pd.read_excel(p) if p.endswith((".xlsx",".xls")) else pd.read_csv(p)
        schema = infer_semantics(df)
        text = dataset_header_text(list(df.columns))
        extras = role_hist_features(schema.roles)
        feats_text = text + " " + " ".join([f"{k}:{v}" for k,v in extras.items()])
        items.append((feats_text, domain))
    return items

def main():
    os.makedirs("models", exist_ok=True)
    items = load_labeled()
    if not items:
        print("Agrega archivos renombrados como 'sales__loquesea.xlsx', 'hr__empleados.csv', etc.")
        return
    X = [t for t,_ in items]
    y = [d for _,d in items]
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1,2), min_df=1)),
        ("clf", LogisticRegression(max_iter=200))
    ])
    pipe.fit(X, y)
    with open("models/domain_clf.pkl","wb") as f:
        pickle.dump(pipe, f)
    print("Guardado: models/domain_clf.pkl")

if __name__ == "__main__":
    main()
