#!/usr/bin/env python3
"""Ask a local Ollama model to answer each silver question.

Choices are labelled A, B, C, D so the model replies with one letter.
The correct letter is shuffled per question. ai_correct compares that letter,
not the original answer text.
"""

from __future__ import annotations

import argparse
import random
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "silver" / "questions.parquet"
ANSWERS_PATH = ROOT / "silver" / "answers.parquet"

MODEL = "llama3.2:3b"
PROMPT_ID = "letter"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LETTERS = "ABCD"
SAVE_EVERY = 20

COLUMNS = [
    "question_id",
    "model_name",
    "prompt_id",
    "prompt_text",
    "correct_letter",
    "ai_answer",
    "ai_correct",
    "response_time",
]


def choices_for(row: pd.Series) -> tuple[list[str], str]:
    """Shuffle the options with a stable seed. Return the choices and the correct letter."""
    options = [row["correct_answer"], *list(row["incorrect_answers"])]
    random.Random(row["question_id"]).shuffle(options)
    correct_letter = LETTERS[options.index(row["correct_answer"])]
    return options, correct_letter


def build_prompt(question: str, options: list[str]) -> str:
    lines = [f"{LETTERS[index]}. {option}" for index, option in enumerate(options)]
    return (
        "Answer with one letter only.\n\n"
        f"Question: {question}\n"
        + "\n".join(lines)
    )


def ask(prompt: str) -> tuple[str, float]:
    started = time.perf_counter()
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 8},
        },
        timeout=120,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    return response.json().get("response", "").strip(), elapsed


def letter_of(answer: str, option_count: int) -> str | None:
    allowed = LETTERS[:option_count]
    match = re.search(rf"\b([{allowed}])\b", answer.upper())
    return match.group(1) if match else None


def load_done(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_parquet(path)


def save(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def run(limit: int | None) -> None:
    questions = pd.read_parquet(QUESTIONS_PATH)
    done = load_done(ANSWERS_PATH)
    finished = set(done["question_id"])
    pending = questions[~questions["question_id"].isin(finished)]
    if limit is not None:
        pending = pending.head(limit)

    print(f"{len(finished)} réponses déjà écrites, {len(pending)} à faire.", flush=True)
    rows = done.to_dict("records")
    new_count = 0

    for _, row in pending.iterrows():
        options, correct_letter = choices_for(row)
        prompt = build_prompt(row["question"], options)
        answer, elapsed = ask(prompt)
        guessed = letter_of(answer, len(options))
        rows.append(
            {
                "question_id": row["question_id"],
                "model_name": MODEL,
                "prompt_id": PROMPT_ID,
                "prompt_text": prompt,
                "correct_letter": correct_letter,
                "ai_answer": answer,
                "ai_correct": guessed == correct_letter,
                "response_time": round(elapsed, 3),
            }
        )
        new_count += 1
        print(
            f"{len(finished) + new_count} {guessed} (bonne lettre {correct_letter}) {elapsed:.1f}s",
            flush=True,
        )
        if new_count % SAVE_EVERY == 0:
            save(pd.DataFrame(rows, columns=COLUMNS), ANSWERS_PATH)

    save(pd.DataFrame(rows, columns=COLUMNS), ANSWERS_PATH)
    print(f"{len(rows)} réponses dans {ANSWERS_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask Ollama to answer the silver questions")
    parser.add_argument("--limit", type=int, default=None, help="Only answer this many new questions")
    args = parser.parse_args()
    run(args.limit)
