"""Streamlit dashboard for the trivia AI benchmark gold tables."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "warehouse" / "trivia.duckdb"

DIFFICULTY_ORDER = ["easy", "medium", "hard"]
COLOR_ACCURACY = "#1f6f5f"
COLOR_COMPARE = ["#1f6f5f", "#c45c26", "#3d5a80", "#7a5c45"]


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(f"SELECT * FROM main_gold.{name}").df()


def run_label(frame: pd.DataFrame) -> pd.Series:
    return frame["model_name"] + " · T=" + frame["temperature"].map(lambda value: f"{value:g}")


def bar_accuracy(frame: pd.DataFrame, x: str, title: str, horizontal: bool = False):
    if frame.empty:
        st.info("Aucune donnée pour ce filtre.")
        return
    chart = frame.copy()
    if x == "difficulty":
        chart["difficulty"] = pd.Categorical(chart["difficulty"], DIFFICULTY_ORDER, ordered=True)
        chart = chart.sort_values("difficulty")
    if horizontal:
        fig = px.bar(
            chart,
            x="accuracy_pct",
            y=x,
            orientation="h",
            title=title,
            text="accuracy_pct",
            color_discrete_sequence=[COLOR_ACCURACY],
        )
        fig.update_layout(xaxis_title="Taux (%)", yaxis_title="")
    else:
        fig = px.bar(
            chart,
            x=x,
            y="accuracy_pct",
            title=title,
            text="accuracy_pct",
            color_discrete_sequence=[COLOR_ACCURACY],
        )
        fig.update_layout(xaxis_title="", yaxis_title="Taux (%)")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        yaxis_range=[0, 100] if not horizontal else None,
        xaxis_range=[0, 100] if horizontal else None,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420 if horizontal else 360,
    )
    st.plotly_chart(fig, use_container_width=True)


st.set_page_config(page_title="Trivia AI Benchmark", layout="wide")
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1100px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Trivia AI Benchmark")
st.caption("Rapport à partir des tables gold DuckDB. Les chiffres viennent de dbt, pas du silver brut.")

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

overall = overall.copy()
overall["run"] = run_label(overall)

st.sidebar.header("Filtres")
models = sorted(overall["model_name"].unique())
model = st.sidebar.selectbox("Modèle", models)
temps = sorted(overall.loc[overall["model_name"] == model, "temperature"].unique())
temperature = st.sidebar.selectbox("Température", temps)
st.sidebar.markdown(
    "Le filtre change les sections du bas. "
    "Le graphique de comparaison montre toujours tous les runs."
)

selected = overall[
    (overall["model_name"] == model) & (overall["temperature"] == temperature)
]
row = selected.iloc[0]

st.subheader("Run sélectionné")
col1, col2, col3 = st.columns(3)
col1.metric("Taux de bonnes réponses", f"{row['accuracy_pct']:.1f} %")
col2.metric("Questions", f"{int(row['n_questions']):,}".replace(",", " "))
col3.metric("Temps moyen", f"{row['avg_response_time_s']:.3f} s")

st.subheader("Comparaison globale")
st.markdown("Tous les modèles et températures, pour lire l'écart d'un coup.")
compare = overall.sort_values(["model_name", "temperature"])
fig_compare = px.bar(
    compare,
    x="run",
    y="accuracy_pct",
    color="model_name",
    text="accuracy_pct",
    color_discrete_sequence=COLOR_COMPARE,
    title="Taux de bonnes réponses par run",
)
fig_compare.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig_compare.update_layout(
    yaxis_range=[0, 100],
    yaxis_title="Taux (%)",
    xaxis_title="",
    legend_title="Modèle",
    margin=dict(l=20, r=20, t=50, b=20),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    height=380,
)
st.plotly_chart(fig_compare, use_container_width=True)
st.dataframe(
    compare[
        [
            "model_name",
            "temperature",
            "n_questions",
            "n_correct",
            "accuracy_pct",
            "avg_response_time_s",
        ]
    ].rename(
        columns={
            "model_name": "modèle",
            "temperature": "température",
            "n_questions": "questions",
            "n_correct": "bonnes réponses",
            "accuracy_pct": "taux %",
            "avg_response_time_s": "temps moyen (s)",
        }
    ),
    width="stretch",
    hide_index=True,
)

left, right = st.columns(2)
with left:
    st.subheader("Par difficulté")
    difficulty = by_difficulty[
        (by_difficulty["model_name"] == model)
        & (by_difficulty["temperature"] == temperature)
    ]
    bar_accuracy(difficulty, "difficulty", "Taux selon la difficulté")
with right:
    st.subheader("Par type")
    question_type = by_type[
        (by_type["model_name"] == model) & (by_type["temperature"] == temperature)
    ]
    bar_accuracy(question_type, "type", "Taux QCM vs vrai/faux")

st.subheader("Par catégorie")
category = by_category[
    (by_category["model_name"] == model) & (by_category["temperature"] == temperature)
].sort_values("accuracy_pct")
bar_accuracy(category, "category", "Taux par catégorie", horizontal=True)
st.dataframe(
    category[
        ["category", "n_questions", "accuracy_pct", "avg_response_time_s"]
    ].rename(
        columns={
            "category": "catégorie",
            "n_questions": "questions",
            "accuracy_pct": "taux %",
            "avg_response_time_s": "temps moyen (s)",
        }
    ),
    width="stretch",
    hide_index=True,
)

st.subheader("Temps de réponse")
timing = by_time[
    (by_time["model_name"] == model) & (by_time["temperature"] == temperature)
].copy()
timing["résultat"] = timing["ai_correct"].map({True: "correct", False: "incorrect"})
st.dataframe(
    timing[
        [
            "résultat",
            "n_questions",
            "avg_response_time_s",
            "min_response_time_s",
            "max_response_time_s",
        ]
    ].rename(
        columns={
            "n_questions": "questions",
            "avg_response_time_s": "temps moyen (s)",
            "min_response_time_s": "min (s)",
            "max_response_time_s": "max (s)",
        }
    ),
    width="stretch",
    hide_index=True,
)
st.caption(
    "Si le temps moyen est proche pour correct et incorrect, "
    "le temps ne sépare pas la qualité des réponses."
)
