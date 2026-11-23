"""Справжні запуски (крок 12): ваша база знань і Gemini, журнал у workbench.db, експорт CSV.

uv run python -m eval.run_real --team 6 --ask 4 --rate --pause 20
Потрібні .env (ключ, сховище, індекс). Запити беруться з eval/requests.json і
eval/questions.json — замініть питання на ті, що відповідають вмісту ВАШОГО сховища.
--rate: після кожного запуску скрипт показує результат і питає вашу оцінку
(1 — добре, 0 — погано, Enter — пропустити). Оцінку ставите ви, не скрипт.
"""
import argparse
import json
import time
from pathlib import Path

import pandas as pd

from workbench.service import build_service

HERE = Path(__file__).parent


def ask_rating(service, run_id: str, preview: str) -> None:
    print(f"\n--- результат ---\n{preview[:700]}\n-----------------")
    answer = input("Оцінка (1 — добре, 0 — погано, Enter — пропустити): ").strip()
    if answer in ("0", "1"):
        service.rate(run_id, positive=answer == "1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", type=int, default=6, help="скільки запусків команди")
    parser.add_argument("--ask", type=int, default=4, help="скільки питань до бази знань")
    parser.add_argument("--pause", type=float, default=15.0, help="пауза між запусками, с (квота)")
    parser.add_argument("--rate", action="store_true", help="питати оцінку після кожного запуску")
    parser.add_argument("--out", default=str(HERE / "runs.csv"))
    args = parser.parse_args()

    requests = [r["request"] for r in json.loads((HERE / "requests.json").read_text("utf-8"))]
    questions = json.loads((HERE / "questions.json").read_text("utf-8"))
    service = build_service()

    for i, request in enumerate(requests[:args.team], 1):
        print(f"[team {i}/{args.team}] {request[:70]}")
        try:
            run = service.run_team(request, on_event=lambda e: print(
                f"   {e['t']:>6}s {e['author']:<16} {e['node']:<18} route={e['route']}"))
            print(f"   stop_reason={run.stop_reason}, LLM calls={sum(run.result.llm_calls.values())}")
            if args.rate:
                ask_rating(service, run.run_id, run.report)
        except Exception as exc:  # 429/503: запуск пропускаємо, журнал не псуємо
            print(f"   пропущено: {type(exc).__name__}")
        time.sleep(args.pause)

    for i, question in enumerate(questions[:args.ask], 1):
        print(f"[ask {i}/{args.ask}] {question}")
        try:
            answer = service.ask(question)
            print(f"   sources={[s['label'] for s in answer.sources]}, invalid={answer.invalid_citations}")
            if args.rate:
                ask_rating(service, answer.run_id, answer.text)
        except Exception as exc:
            print(f"   пропущено: {type(exc).__name__}")
        time.sleep(args.pause)

    rows = service.history.list(limit=1000)
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\nЖурнал: {len(rows)} запусків -> {args.out}; середнє: {service.history.summary()}")


if __name__ == "__main__":
    main()
