import pandas as pd
from app.application.recommender import auto_dashboard_spec
from app.application.semantics import infer_semantics
from app.application.spec_guard import validate_dashboard

def _load(path):  # usa tus sample_data
    return pd.read_csv(path)

def test_sales_sample_spec_ok():
    df = _load("sample_data/sales_small.csv")
    schema = infer_semantics(df)
    spec = auto_dashboard_spec(df, roles=schema.roles, source_name="sales_small.csv", process_id="dev")
    h = validate_dashboard(df, spec, roles=schema.roles)
    assert h.score >= 70
    assert not h.blocking
