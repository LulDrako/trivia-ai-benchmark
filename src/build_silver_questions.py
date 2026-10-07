#!/usr/bin/env python3
"""Build silver/questions.parquet from the raw bronze CSV.

The bronze file keeps OpenTDB HTML entities. This step decodes them,
deduplicates identical MCQs, and assigns a stable id. It does not call a model.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "bronze" / "questions_raw.csv"
DEFAULT_OUTPUT = ROOT / "silver" / "questions.parquet"
ANSWER_FILES = (
    ROOT / "silver" / "answers.parquet",
    ROOT / "silver" / "answers_qwen.parquet",
)

COLUMNS = [
    "question_id",
    "category",
    "type",
    "difficulty",
    "question",
    "correct_answer",
    "incorrect_answers",
]


def content_key(question: str, correct_answer: str, incorrect_answers: list[str]) -> str:
    """Identity of an MCQ: same stem + answers = same question, category ignored."""
    return "\n".join(
        [question, correct_answer, *sorted(incorrect_answers)]
    )


def stable_id(question: str, correct_answer: str, incorrect_answers: list[str]) -> str:
    """Hash the cleaned MCQ content so the same question keeps the same id."""
    return hashlib.sha256(
        content_key(question, correct_answer, incorrect_answers).encode("utf-8")
    ).hexdigest()


def decode_answers(value: str) -> list[str]:
    answers = json.loads(value)
    return [html.unescape(str(answer)).strip() for answer in answers]


def remap_answers(old: pd.DataFrame, new: pd.DataFrame) -> None:
    """Rewrite answer files so question_id follows the new silver ids."""
    old = old.copy()
    new = new.copy()
    old["_key"] = [
        content_key(q, c, list(i))
        for q, c, i in zip(old["question"], old["correct_answer"], old["incorrect_answers"])
    ]
    new["_key"] = [
        content_key(q, c, list(i))
        for q, c, i in zip(new["question"], new["correct_answer"], new["incorrect_answers"])
    ]
    id_map = (
        old[["question_id", "_key"]]
        .merge(new[["question_id", "_key"]], on="_key", suffixes=("_old", ""))
        .drop_duplicates(subset=["question_id_old"])
        .set_index("question_id_old")["question_id"]
    )

    for path in ANSWER_FILES:
        if not path.exists():
            continue
        answers = pd.read_parquet(path)
        before = len(answers)
        answers["question_id"] = answers["question_id"].map(id_map)
        answers = answers.dropna(subset=["question_id"])
        # Same MCQ may have had two bronze rows → two answer rows; keep one.
        subset = [c for c in ("question_id", "model_name", "prompt_id", "temperature") if c in answers.columns]
        answers = answers.drop_duplicates(subset=subset, keep="first")
        answers.to_parquet(path, index=False)
        print(f"{path.name}: {before} → {len(answers)} réponses")


def build(input_path: Path, output_path: Path) -> int:
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    old = pd.read_parquet(output_path) if output_path.exists() else None

    question = raw["question"].map(lambda value: html.unescape(value).strip())
    correct_answer = raw["correct_answer"].map(lambda value: html.unescape(value).strip())
    incorrect_answers = raw["incorrect_answers"].map(decode_answers)

    clean = pd.DataFrame(
        {
            "question_id": [
                stable_id(q, c, list(i))
                for q, c, i in zip(question, correct_answer, incorrect_answers)
            ],
            "category": raw["category"].map(lambda value: html.unescape(value).strip()),
            "type": raw["type"].str.strip().str.lower(),
            "difficulty": raw["difficulty"].str.strip().str.lower(),
            "question": question,
            "correct_answer": correct_answer,
            "incorrect_answers": incorrect_answers,
        }
    )

    before = len(clean)
    clean = clean.drop_duplicates(subset=["question_id"], keep="first").reset_index(drop=True)
    dropped = before - len(clean)
    if dropped:
        print(f"{dropped} doublon(s) MCQ retirés ({before} → {len(clean)})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(output_path, index=False)

    if old is not None:
        remap_answers(old, clean)

    return len(clean)


if __name__ == "__main__":
    count = build(DEFAULT_INPUT, DEFAULT_OUTPUT)
    print(f"{count} questions écrites dans {DEFAULT_OUTPUT}")
