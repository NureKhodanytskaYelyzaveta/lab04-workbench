"""Робоче місце гейм-дизайнера: база знань + команда проєктування горор-сцени.

Запуск: uv run streamlit run streamlit_app.py
Інтерфейс не викликає агентів і базу даних напряму: лише методи WorkbenchService.
"""
import os

import pandas as pd
import streamlit as st

from workbench.service import WorkbenchService, build_service

MAX_TEAM_RUNS = 10  # захист квоти: запусків команди за сесію
MAX_ASK_QUESTIONS = 30  # питань до бази знань за сесію

NODE_LABELS = {
    "intake": "Перевірка запиту", "retrieve_context": "Пошук правил у базі знань",
    "scene_designer": "Дизайнер сцени пише чернетку", "scene_check": "Перевірка структури сцени",
    "audio_designer": "Саунд-дизайнер", "visual_designer": "VFX-художник",
    "plans": "Збирання планів звуку і візуалу", "link_check": "Перевірка посилань на біти",
    "director": "Креативний директор", "gate": "Рішення директора",
    "publish": "Формування звіту", "reject": "Запит відхилено",
}

st.set_page_config(page_title="Робоче місце гейм-дизайнера", page_icon="🕯️", layout="wide")


def safe_error(exc: Exception) -> str:
    """Текст помилки для екрана: без ключа API, якщо він раптом є в повідомленні."""
    text = f"{type(exc).__name__}: {exc}"[:300]
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        secret = os.getenv(name)
        if secret:
            text = text.replace(secret, "***")
    return text


@st.cache_resource
def cached_service() -> WorkbenchService:
    return build_service()


def get_service() -> WorkbenchService | None:
    if "service" in st.session_state:  # тести і демонстраційний режим підставляють свій сервіс
        return st.session_state["service"]
    try:
        return cached_service()
    except Exception as exc:  # немає ключа, індексу чи сховища
        st.error(f"Не вдалося запустити сервіс: {safe_error(exc)}")
        st.info("Перевірте .env (GEMINI_API_KEY, OBSIDIAN_VAULT, CHROMA_PATH) "
                "і виконайте індексацію: uv run python -m kb.indexer")
        return None


service = get_service()
if service is None:
    st.stop()

state = st.session_state
state.setdefault("messages", [])
state.setdefault("team_runs", 0)
state.setdefault("ask_count", 0)

tab_ask, tab_team, tab_history = st.tabs(
    ["Питання до бази знань", "Команда агентів", "Історія і метрики"])

# ---------------------------------------------------------------- UC1: база знань
with tab_ask:
    for message in state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Запитайте про правила дизайну і технічні практики проєкту",
                             disabled=state.ask_count >= MAX_ASK_QUESTIONS)
    if question:
        state.ask_count += 1
        state.messages.append({"role": "user", "content": question})
        try:
            with st.status("Агент шукає в базі знань…", expanded=False) as status:
                def log(event: dict) -> None:
                    if event["author"] != "user" and event["text"]:
                        status.write(f"{event['author']}: {event['text'][:80]}")

                answer = service.ask(question, on_event=log)
                status.update(label="Відповідь готова", state="complete")
            sources = "\n".join(f"- [{s['label']}]({s['url']})" for s in answer.sources)
            content = answer.linked_text + (
                f"\n\n**Фрагменти, знайдені агентом:**\n{sources}" if sources else "")
            if answer.invalid_citations:
                content += ("\n\n:warning: Посилання без підтвердження: "
                            + ", ".join(answer.invalid_citations))
        except Exception as exc:  # квота, мережа, збій моделі
            content = f":x: Не вдалося отримати відповідь. {safe_error(exc)}"
        state.messages.append({"role": "assistant", "content": content})
        st.rerun()

# ---------------------------------------------------------------- UC2-UC4: команда агентів
with tab_team:
    with st.form("team_form"):
        request = st.text_area(
            "Опис сцени", height=120,
            placeholder="Герой заходить у покинуту дитячу лікарню, де чути дитячий сміх.")
        submitted = st.form_submit_button("Запустити команду",
                                          disabled=state.team_runs >= MAX_TEAM_RUNS)
    if submitted and request.strip():
        state.team_runs += 1
        try:
            with st.status("Команда працює…", expanded=True) as status:
                def show(event: dict) -> None:
                    base = event["node"].split("@")[0]
                    if base in NODE_LABELS:
                        route = f" → {event['route']}" if event["route"] else ""
                        status.write(f"{NODE_LABELS[base]}{route}")

                state.last_run = service.run_team(request.strip(), on_event=show)
                status.update(label="Готово", state="complete", expanded=False)
        except Exception as exc:
            state.pop("last_run", None)
            st.error(f"Команда не завершила роботу. {safe_error(exc)}")

    run = state.get("last_run")
    if run:
        cols = st.columns(5)
        cols[0].metric("Чернеток", run.result.state.get("drafts", "—"))
        cols[1].metric("Викликів LLM", sum(run.result.llm_calls.values()))
        cols[2].metric("Токенів", run.result.tokens)
        cols[3].metric("Час, с", run.result.seconds)
        cols[4].metric("Фрагментів з БЗ", len(run.kb_sources))
        if not run.ok:
            st.warning(run.report or "Запит відхилено.")
        else:
            curve = [round(b.get("fear_target", 0) / 100, 2) for b in run.scene.get("beats", [])]
            ids = [b.get("id", str(i)) for i, b in enumerate(run.scene.get("beats", []), 1)]
            st.caption("Крива страху (0..1) для FearLevelController")
            st.line_chart(pd.DataFrame({"страх": curve}, index=ids))
            st.markdown(run.report)
            if run.kb_sources:
                with st.expander("Контекст з бази знань, який отримав дизайнер сцени"):
                    st.markdown("\n".join(f"- [{s['label']}]({s['url']})" for s in run.kb_sources))
            c1, c2, c3 = st.columns(3)
            c1.download_button("Завантажити сцену .md", run.report, file_name="scene.md")
            c2.download_button("Завантажити .json", run.scene_json, file_name="scene.json")
            c3.download_button("Завантажити .yarn", run.yarn, file_name="scene.yarn")

            st.subheader("Перевірка людиною")
            record = service.history.get(run.run_id) or {}
            already_saved = bool(record.get("saved_path"))
            reviewer = st.text_input("Ваше ім'я")
            confirmed = st.checkbox("Я перевірив сцену, криву страху, звук і ефекти")
            can_save = confirmed and bool(reviewer.strip()) and not already_saved
            if st.button("Зберегти в Obsidian (Inbox)", disabled=not can_save):
                try:
                    path = service.save_scene(run, reviewer, confirmed=confirmed)
                    st.success(f"Збережено: {path.name}. Переіндексуйте базу знань.")
                except (ValueError, PermissionError, RuntimeError) as exc:
                    st.error(f"Не збережено: {exc}")
            if already_saved:
                st.caption("Цей запуск уже збережено в Inbox.")
        rating = st.feedback("thumbs", key=f"rate_{run.run_id}")
        if rating is not None:
            service.rate(run.run_id, positive=bool(rating))

# ---------------------------------------------------------------- UC5: історія і метрики
with tab_history:
    summary = service.history.summary()
    cols = st.columns(4)
    cols[0].metric("Запусків", summary["runs"] or 0)
    cols[1].metric("Сер. викликів LLM", round(summary["avg_calls"] or 0, 1))
    cols[2].metric("Сер. час, с", round(summary["avg_seconds"] or 0, 1))
    share = summary["positive_share"]
    cols[3].metric("Позитивних оцінок", "—" if share is None else f"{share:.0%}")
    rows = service.history.list()
    if rows:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, hide_index=True)
        st.download_button("Експорт CSV", frame.to_csv(index=False).encode("utf-8-sig"),
                           file_name="runs.csv", mime="text/csv")
    else:
        st.caption("Запусків ще немає.")

# Бічну панель малюємо останньою, щоб лічильник уже враховував поточний запуск
with st.sidebar:
    st.header("Робоче місце гейм-дизайнера")
    st.caption("Етап ЖЦ ПЗ: проєктування")
    st.metric("Запусків команди в сесії", f"{state.team_runs} / {MAX_TEAM_RUNS}")
    st.caption(f"Сховище Obsidian: {service.vault_name or 'не налаштовано'}")
