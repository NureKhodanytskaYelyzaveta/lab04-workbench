# lab04-workbench — робоче місце гейм-дизайнера

Вебзастосунок на Streamlit для етапу ЖЦ ПЗ **«3 Проєктування»**: об'єднує базу знань
Obsidian + Chroma (ЛР 2) і команду агентів на Google ADK (ЛР 3, проєктування сцени
психологічного горору для Unity).

Три вкладки: **Питання до бази знань** (чат з посиланнями `obsidian://`), **Команда агентів**
(хід роботи, крива страху, експорт `scene.md` / `scene.json` / `scene.yarn`, збереження в `Inbox/`
лише після підтвердження людини), **Історія і метрики** (журнал SQLite, експорт CSV).

```bash
uv sync
cp .env.example .env                      # ключ, шляхи до сховища й індексу
uv run python -m kb.indexer               # якщо індекс ще не побудовано (або CHROMA_PATH з ЛР 2)
uv run streamlit run streamlit_app.py     # http://localhost:8501

uv run pytest -q                          # тести без API
PYTHONPATH=. uv run streamlit run tests/demo_app.py   # демо-режим без ключа
uv run python -m eval.run_real --team 6 --ask 4 --rate --pause 20   # справжні запуски + CSV
uv run python -m eval.sus eval/sus_responses.csv                     # SUS
```

Шари: `streamlit_app.py` → `workbench/service.py` → `app/` (граф), `kb/` (знання),
`workbench/storage.py` (SQLite), `workbench/exporters.py` (артефакти). Докладно: `docs/architecture.md`.
Паспорт: `WORKBENCH-CARD.md`. Звіт: `docs/report.md`. Ліцензія: MIT.
