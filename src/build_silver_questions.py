#!/usr/bin/env python3
"""Build silver/questions.parquet from the raw bronze CSV.

The bronze file keeps OpenTDB HTML entities. This step decodes them and
assigns a stable id. It does not call a model.
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

COLUMNS = [
    "question_id",
    "category",
    "type",
    "difficulty",
    "question",
    "correct_answer",
    "incorrect_answers",
]


def stable_id(raw: pd.Series) -> str:
    """Hash the raw bronze fields so the same question keeps the same id."""
    key = "\n".join(
        [
            raw["category"],
            raw["type"],
            raw["difficulty"],
            raw["question"],
            raw["correct_answer"],
            raw["incorrect_answers"],
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def decode_answers(value: str) -> list[str]:
    answers = json.loads(value)
    return [html.unescape(str(answer)).strip() for answer in answers]


def build(input_path: Path, output_path: Path) -> int:
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    clean = pd.DataFrame(
        {
            "question_id": raw.apply(stable_id, axis=1),
            "category": raw["category"].map(lambda value: html.unescape(value).strip()),
            "type": raw["type"].str.strip().str.lower(),
            "difficulty": raw["difficulty"].str.strip().str.lower(),
            "question": raw["question"].map(lambda value: html.unescape(value).strip()),
            "correct_answer": raw["correct_answer"].map(lambda value: html.unescape(value).strip()),
            "incorrect_answers": raw["incorrect_answers"].map(decode_answers),
        }
    )
    duplicated = int(clean["question_id"].duplicated().sum())
    if duplicated:
        raise SystemExit(f"{duplicated} identifiants en double, le silver n'a pas été écrit.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(output_path, index=False)
    return len(clean)


if __name__ == "__main__":
    count = build(DEFAULT_INPUT, DEFAULT_OUTPUT)
    print(f"{count} questions écrites dans {DEFAULT_OUTPUT}")
