"""Answer the demo's example questions once, at build time, and save them to web.answer_cache.

Answers are deterministic (temperature 0, fixed seed), so the cache gives what a live run
would, without the minutes a CPU-only Space needs per answer.
"""

import json
from dataclasses import asdict

from fonti.config import load_settings
from fonti.service import Fonti


def main() -> None:
    settings = load_settings()
    if settings.web.answer_cache is None:
        raise SystemExit("web.answer_cache is not set")
    fonti = Fonti(settings)
    answers = {}
    for question in settings.web.example_questions:
        answers[question] = asdict(fonti.ask(question))
        print(f"answered: {question}", flush=True)
    settings.web.answer_cache.write_text(
        json.dumps(answers, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
