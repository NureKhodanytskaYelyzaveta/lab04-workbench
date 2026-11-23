"""Тести інтерфейсу Streamlit без браузера (streamlit.testing.v1.AppTest)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.fixtures import REQUEST

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def start(service) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["service"] = service  # підмінний сервіс замість Gemini
    return at.run()


def save_button(at):
    return next(b for b in at.button if b.label == "Зберегти в Obsidian (Inbox)")


def test_three_tabs_and_no_errors(service):
    at = start(service)
    assert not at.exception
    assert [t.label for t in at.tabs] == [
        "Питання до бази знань", "Команда агентів", "Історія і метрики"]


def test_chat_answer_with_sources_and_history_kept(service):
    at = start(service)
    at.chat_input[0].set_value("Як будувати криву страху?").run()
    assistant = [m for m in at.chat_message if m.name == "assistant"]
    text = assistant[-1].markdown[0].value
    assert "obsidian://open?vault=horror-handbook" in text
    assert "Фрагменти, знайдені агентом" in text
    assert len(at.session_state["messages"]) == 2  # історія чату зберігається між діями


def test_team_run_shows_artifacts_and_metrics(service):
    at = start(service)
    at.text_area[0].input(REQUEST)
    at.button[0].click().run()  # кнопка форми «Запустити команду»
    assert not at.exception
    assert any("Біти і крива страху" in md.value for md in at.markdown)
    assert at.session_state["team_runs"] == 1
    assert len(at.metric) >= 5


def test_human_in_the_loop_blocks_saving_until_confirmed(service):
    at = start(service)
    at.text_area[0].input(REQUEST)
    at.button[0].click().run()
    assert save_button(at).disabled  # без підтвердження зберегти не можна
    at.text_input[0].input("Іваненко").run()
    assert save_button(at).disabled  # ім'я є, прапорця немає
    at.checkbox[0].check().run()
    save_button(at).click().run()
    assert any("Збережено" in s.value for s in at.success)
    assert list((service.vault / "Inbox").glob("*.md"))
    at.run()  # наступний цикл скрипта: запуск уже збережено
    assert save_button(at).disabled  # повторне збереження того самого запуску заблоковано


def test_team_run_limit_disables_button(service):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["service"] = service
    at.session_state["team_runs"] = 10
    at.run()
    assert at.button[0].disabled


def test_missing_configuration_is_reported(monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT", "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert "Не вдалося запустити сервіс" in at.error[0].value
