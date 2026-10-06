#!/usr/bin/env python3
"""Récupère l'intégralité d'OpenTDB dans bronze/questions_raw.csv.

OpenTDB n'est pas une API paginée : chaque appel renvoie un tirage aléatoire.
Un token de session mémorise les questions déjà données, jusqu'au code 4
(plus aucune question nouvelle).

Contraintes de l'API :
- 50 questions maximum par appel
- 1 appel toutes les 5 secondes
- code 5 : trop d'appels, on attend et on réessaie
- code 1 : pas assez de questions pour la quantité demandée, on réduit
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

API_URL = "https://opentdb.com/api.php"
TOKEN_URL = "https://opentdb.com/api_token.php"
COUNT_URL = "https://opentdb.com/api_count_global.php"

MAX_AMOUNT = 50
PAUSE_SECONDS = 5.0
TIMEOUT_SECONDS = 30

COLUMNS = [
    "category",
    "type",
    "difficulty",
    "question",
    "correct_answer",
    "incorrect_answers",
]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "bronze" / "questions_raw.csv"
DEFAULT_SESSION = ROOT / "bronze" / "session.json"


class RateLimiter:
    """Garantit un écart minimum entre deux appels HTTP."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._last = 0.0

    def wait(self) -> None:
        if self._last == 0.0:
            return
        remaining = self.interval - (time.monotonic() - self._last)
        if remaining > 0:
            time.sleep(remaining)

    def mark(self) -> None:
        self._last = time.monotonic()


def get_json(session: requests.Session, limiter: RateLimiter, url: str, params: dict | None = None) -> dict:
    """Appelle OpenTDB en respectant le rate limit. Réessaie sur le code 5."""
    while True:
        limiter.wait()
        try:
            response = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
        except requests.exceptions.SSLError:
            raise SystemExit(
                "Le certificat HTTPS est intercepté par un proxy. "
                "Coupe le VPN ou le proxy de l'école, puis relance le script."
            )
        limiter.mark()

        if response.status_code == 403:
            raise SystemExit(
                "Accès refusé à OpenTDB (HTTP 403). "
                "Le réseau actuel bloque le site. "
                "Coupe le VPN ou le proxy de l'école, ou utilise un partage de connexion, puis relance."
            )
        response.raise_for_status()
        payload = response.json()

        if payload.get("response_code") == 5:
            print("Rate limit atteint (code 5). Nouvel essai après la pause.", flush=True)
            continue
        return payload


def request_token(http: requests.Session, limiter: RateLimiter) -> str:
    payload = get_json(http, limiter, TOKEN_URL, {"command": "request"})
    if payload.get("response_code") != 0 or "token" not in payload:
        raise SystemExit(f"Impossible d'obtenir un token de session : {payload}")
    return payload["token"]


def verified_question_count(http: requests.Session, limiter: RateLimiter) -> int | None:
    payload = get_json(http, limiter, COUNT_URL)
    overall = payload.get("overall") or {}
    count = overall.get("total_num_of_verified_questions")
    return int(count) if count is not None else None


def load_session(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(path: Path, token: str, rows: int, done: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"token": token, "rows": rows, "done": done}, indent=2),
        encoding="utf-8",
    )


def count_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def append_questions(path: Path, questions: list[dict], write_header: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if write_header else "a"
    with path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        for question in questions:
            writer.writerow(
                {
                    "category": question["category"],
                    "type": question["type"],
                    "difficulty": question["difficulty"],
                    "question": question["question"],
                    "correct_answer": question["correct_answer"],
                    "incorrect_answers": json.dumps(
                        question["incorrect_answers"], ensure_ascii=False
                    ),
                }
            )


def scrape(output: Path, session_path: Path, reset: bool) -> None:
    if reset:
        output.unlink(missing_ok=True)
        session_path.unlink(missing_ok=True)

    existing = load_session(session_path)
    if existing and existing.get("done"):
        print(f"Déjà terminé : {existing.get('rows', 0)} questions dans {output}")
        return

    if output.exists() and existing is None:
        raise SystemExit(
            f"{output} existe déjà sans fichier de reprise. "
            "Relance avec --reset pour recommencer, ou restaure bronze/session.json."
        )

    limiter = RateLimiter(PAUSE_SECONDS)
    http = requests.Session()
    http.headers["User-Agent"] = "trivia-ai-benchmark/bronze"

    expected = verified_question_count(http, limiter)
    if expected is not None:
        print(f"OpenTDB annonce {expected} questions vérifiées.", flush=True)

    if existing:
        token = existing["token"]
        written = count_data_rows(output)
        print(f"Reprise : {written} questions déjà écrites.", flush=True)
    else:
        token = request_token(http, limiter)
        written = 0
        save_session(session_path, token, written, done=False)
        print("Token de session obtenu.", flush=True)

    amount = MAX_AMOUNT
    started = time.monotonic()

    while True:
        payload = get_json(
            http,
            limiter,
            API_URL,
            {"amount": amount, "token": token},
        )
        code = payload.get("response_code")

        if code == 0:
            batch = payload.get("results") or []
            append_questions(output, batch, write_header=written == 0)
            written += len(batch)
            save_session(session_path, token, written, done=False)
            amount = MAX_AMOUNT
            elapsed = time.monotonic() - started
            print(f"{written} questions écrites ({elapsed:.0f}s)", flush=True)
            continue

        if code == 4:
            save_session(session_path, token, written, done=True)
            print(f"Terminé (code 4). {written} questions dans {output}")
            if expected is not None and written < expected:
                print(
                    f"Attention : OpenTDB annonçait {expected} questions vérifiées, "
                    f"le token en a renvoyé {written}."
                )
            return

        if code == 1:
            if amount == 1:
                save_session(session_path, token, written, done=True)
                print(f"Plus de question disponible. {written} questions dans {output}")
                return
            amount = max(1, amount // 2)
            print(f"Pas assez de questions pour ce tirage (code 1). Nouvel essai avec {amount}.", flush=True)
            continue

        raise SystemExit(f"Réponse OpenTDB inattendue (code {code}) : {payload}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape OpenTDB vers bronze/questions_raw.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--session", type=Path, default=DEFAULT_SESSION)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Efface le CSV et le token, puis recommence depuis zéro",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        scrape(args.output, args.session, args.reset)
    except requests.RequestException as exc:
        print(f"Erreur réseau : {exc}", file=sys.stderr)
        sys.exit(1)
