"""Streamlit dashboard for the trivia AI benchmark gold tables."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "warehouse" / "trivia.duckdb"


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(f"SELECT * FROM main_gold.{name}").df()


def filter_frame(frame: pd.DataFrame, model: str, temperature: Optional[float]) -> pd.DataFrame:
    filtered = frame[frame["model_name"] == model]
    if temperature is not None and "temperature" in filtered.columns:
        filtered = filtered[filtered["temperature"] == temperature]
    return filtered


st.set_page_config(page_title="Trivia AI Benchmark", layout="wide")
st.title("Trivia AI Benchmark")
st.caption("Rapport interactif à partir des tables gold DuckDB.")

if not DB_PATH.exists():
    st.error(
        "Base introuvable. Lance d'abord `dbt run --profiles-dir .` "
        "pour créer warehouse/trivia.duckdb."
    )
    st.stop()

overall = load_table("performance_overall")
by_category = load_table("performance_by_category")
by_difficulty = load_table("performance_by_difficulty")
by_type = load_table("performance_by_type")
by_time = load_table("performance_response_time")

models = sorted(overall["model_name"].unique())
model = st.sidebar.selectbox("Modèle", models)
temps = sorted(overall.loc[overall["model_name"] == model, "temperature"].unique())
temperature = st.sidebar.selectbox("Température", temps)

selected = filter_frame(overall, model, temperature)
if selected.empty:
    st.warning("Aucune ligne pour ce filtre.")
    st.stop()

row = selected.iloc[0]
col1, col2, col3 = st.columns(3)
col1.metric("Taux de bonnes réponses", f"{row['accuracy_pct']} %")
col2.metric("Questions", int(row["n_questions"]))
col3.metric("Temps moyen", f"{row['avg_response_time_s']} s")

st.subheader("Comparaison des modèles")
st.dataframe(overall, width="stretch")
st.bar_chart(
    overall.assign(label=overall["model_name"] + " T=" + overall["temperature"].astype(str)).set_index(
        "label"
    )["accuracy_pct"]
)

st.subheader("Par difficulté")
difficulty = filter_frame(by_difficulty, model, temperature)
st.bar_chart(difficulty.set_index("difficulty")["accuracy_pct"])
st.dataframe(difficulty, width="stretch")

st.subheader("Par catégorie")
category = filter_frame(by_category, model, temperature).sort_values("accuracy_pct", ascending=True)
st.bar_chart(category.set_index("category")["accuracy_pct"])
st.dataframe(category, width="stretch")

st.subheader("Par type de question")
question_type = filter_frame(by_type, model, temperature)
st.bar_chart(question_type.set_index("type")["accuracy_pct"])
st.dataframe(question_type, width="stretch")

st.subheader("Temps de réponse")
timing = filter_frame(by_time, model, temperature)
st.dataframe(timing, width="stretch")
