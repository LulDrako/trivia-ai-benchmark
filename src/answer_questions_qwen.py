#!/usr/bin/env python3
"""Ask a local Qwen model to answer each silver question.

Results are stored separately from the Llama benchmark so both models can be
compared on the same questions, choices, and prompt format.
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
ANSWERS_PATH = ROOT / "silver" / "asnwers_qwen.parquet"

# A compact, free-to-run local model. Download it once with:
#   ollama pull qwen2.5:3b
MODEL = "qwen2.5:3b"
PROMPT_ID = "letter"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LETTERS = "ABCD"
SAVE_EVERY = 20
DEFAULT_TEMPERATURES = (0.0, 0.5, 1.0)

COLUMNS = [
    "question_id",
    "model_name",
    "prompt_id",
    "temperature",
    "prompt_text",
    "correct_letter",
    "ai_answer",
    "ai_correct",
    "response_time",
]


def choices_for(row: pd.Series) -> tuple[list[str], str]:
    """Shuffle options reproducibly, returning the choices and correct letter."""
    options = [row["correct_answer"], *list(row["incorrect_answers"])]
    random.Random(row["question_id"]).shuffle(options)
    return options, LETTERS[options.index(row["correct_answer"])]


def build_prompt(question: str, options: list[str]) -> str:
    choices = [f"{LETTERS[index]}. {option}" for index, option in enumerate(options)]
    return "Answer with one letter only.\n\n" f"Question: {question}\n" + "\n".join(choices)


def ask(prompt: str, temperature: float) -> tuple[str, float]:
    started = time.perf_counter()
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 8},
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
    done = pd.read_parquet(path)
    # Compatibility with a result file created before temperature was tracked:
    # its answers were generated at the former fixed value, 0.0.
    if "temperature" not in done.columns:
        done["temperature"] = 0.0
    return done.reindex(columns=COLUMNS)


def save(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def run(limit: int | None, temperatures: tuple[float, ...]) -> None:
    questions = pd.read_parquet(QUESTIONS_PATH)
    done = load_done(ANSWERS_PATH)
    finished = set(zip(done["question_id"], done["temperature"]))
    pending = [
        (row, temperature)
        for _, row in questions.iterrows()
        for temperature in temperatures
        if (row["question_id"], temperature) not in finished
    ]
    if limit is not None:
        pending = pending[:limit]

    print(
        f"Températures : {', '.join(map(str, temperatures))}. "
        f"{len(finished)} réponses déjà écrites, {len(pending)} à faire.",
        flush=True,
    )
    rows = done.to_dict("records")
    new_count = 0

    for row, temperature in pending:
        options, correct_letter = choices_for(row)
        prompt = build_prompt(row["question"], options)
        answer, elapsed = ask(prompt, temperature)
        guessed = letter_of(answer, len(options))
        rows.append(
            {
                "question_id": row["question_id"],
                "model_name": MODEL,
                "prompt_id": PROMPT_ID,
                "temperature": temperature,
                "prompt_text": prompt,
                "correct_letter": correct_letter,
                "ai_answer": answer,
                "ai_correct": guessed == correct_letter,
                "response_time": round(elapsed, 3),
            }
        )
        new_count += 1
        print(
            f"{len(finished) + new_count} T={temperature}: {guessed} "
            f"(bonne lettre {correct_letter}) {elapsed:.1f}s",
            flush=True,
        )
        if new_count % SAVE_EVERY == 0:
            save(pd.DataFrame(rows, columns=COLUMNS), ANSWERS_PATH)

    save(pd.DataFrame(rows, columns=COLUMNS), ANSWERS_PATH)
    print(f"{len(rows)} réponses Qwen dans {ANSWERS_PATH}")


def parse_temperatures(value: str) -> tuple[float, ...]:
    try:
        temperatures = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Utilisez des nombres séparés par des virgules.") from exc
    if not temperatures or any(temperature < 0 for temperature in temperatures):
        raise argparse.ArgumentTypeError("Indiquez au moins une température positive ou nulle.")
    if len(set(temperatures)) != len(temperatures):
        raise argparse.ArgumentTypeError("Chaque température doit être indiquée une seule fois.")
    return temperatures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask Qwen through Ollama to answer silver questions")
    parser.add_argument("--limit", type=int, default=None, help="Only answer this many new questions")
    parser.add_argument(
        "--temperatures",
        type=parse_temperatures,
        default=DEFAULT_TEMPERATURES,
        help="Comma-separated temperatures (default: 0,0.5,1.0)",
    )
    args = parser.parse_args()
    run(args.limit, args.temperatures)
