"""Логіка сервісу з підмінною функцією запуску: без ADK, Chroma і мережі.

Перевіряє правила, що не залежать від моделей: джерела відповіді, непідтверджені
посилання, артефакти, людина в циклі, журнал. Повні сценарії з графом — test_service.py.
"""
import pytest

from tests.fixtures import APPROVE, AUDIO, GOOD, VISUAL
from workbench.runner import RunResult
from workbench.service import WorkbenchService
from workbench.storage import HistoryStore

FRAGMENT = ('<fragment source="[[Крива страху#Правила]]" path="Дизайн/Крива страху.md" '
            'distance="0.300">\nтекст\n</fragment>')


def make_service(tmp_path, result: RunResult) -> WorkbenchService:
    vault = tmp_path / "vault"
    vault.mkdir()
    return WorkbenchService(
        team_agent=None, kb_agent=None, history=HistoryStore(tmp_path / "h.db"),
        vault=vault, vault_name="my vault", run_fn=lambda agent, text, on_event=None: result)


def team_result(**state) -> RunResult:
    base = {"scene": GOOD, "audio_plan": AUDIO, "visual_plan": VISUAL, "verdict": APPROVE,
            "drafts": 1, "stop_reason": "approved", "report": "# Дитяче відділення\n",
            "kb_context": FRAGMENT}
    return RunResult(state={**base, **state}, trace=[], final_text="x",
                     llm_calls={"scene_designer": 1, "director": 1}, tokens=50, seconds=1.2)


def test_ask_extracts_sources_from_tool_output_and_builds_obsidian_links(tmp_path):
    result = RunResult(state={}, trace=[], tool_outputs=[FRAGMENT],
                       final_text="Починайте спокійно [[Крива страху#Правила]].",
                       llm_calls={"kb_assistant": 2}, tokens=10, seconds=0.5)
    answer = make_service(tmp_path, result).ask("Як будувати криву страху?")
    assert [s["label"] for s in answer.sources] == ["Крива страху#Правила"]
    assert answer.sources[0]["url"].startswith("obsidian://open?vault=my%20vault&file=")
    assert "%D0%94" in answer.sources[0]["url"]  # кирилиця в шляху закодована
    assert answer.invalid_citations == []
    assert "](obsidian://open?vault=my%20vault" in answer.linked_text


def test_ask_flags_citation_of_note_that_was_never_found(tmp_path):
    result = RunResult(state={}, trace=[], tool_outputs=[FRAGMENT],
                       final_text="Так [[Вигадана нотатка#Розділ]].",
                       llm_calls={"kb_assistant": 1}, tokens=0, seconds=0.1)
    answer = make_service(tmp_path, result).ask("питання")
    assert answer.invalid_citations == ["Вигадана нотатка#Розділ"]
    assert "[[Вигадана нотатка#Розділ]]" in answer.linked_text  # не стає посиланням


def test_run_team_builds_artifacts_and_logs_metrics(tmp_path):
    service = make_service(tmp_path, team_result())
    run = service.run_team("Герой заходить у покинуту дитячу лікарню.")
    assert run.ok and '"fear_curve"' in run.scene_json and run.yarn.startswith("title: Scene_")
    assert [s["label"] for s in run.kb_sources] == ["Крива страху#Правила"]
    row = service.history.get(run.run_id)
    assert row["kind"] == "team" and row["llm_calls"] == 2 and row["stop_reason"] == "approved"


def test_rejected_request_has_no_artifacts_and_cannot_be_saved(tmp_path):
    rejected = RunResult(state={}, trace=[], final_text="Запит відхилено: коротко",
                         llm_calls={}, tokens=0, seconds=0.0)
    service = make_service(tmp_path, rejected)
    run = service.run_team("жах")
    assert not run.ok and run.scene_json == "" and run.yarn == ""
    assert service.history.get(run.run_id)["stop_reason"] == "rejected"
    with pytest.raises(ValueError):
        service.save_scene(run, "Іваненко", confirmed=True)


def test_save_requires_confirmation_and_reviewer_name(tmp_path):
    service = make_service(tmp_path, team_result())
    run = service.run_team("Герой заходить у покинуту дитячу лікарню.")
    with pytest.raises(PermissionError):
        service.save_scene(run, "Іваненко", confirmed=False)
    with pytest.raises(ValueError):
        service.save_scene(run, "  ", confirmed=True)
    assert not (service.vault / "Inbox").exists()  # без підтвердження нічого не записано
    path = service.save_scene(run, "Іваненко", confirmed=True)
    assert path.parent.name == "Inbox"
    assert 'approved_by: "Іваненко"' in path.read_text(encoding="utf-8")
    assert service.history.get(run.run_id)["saved_path"] == str(path)


def test_same_run_cannot_be_saved_twice(tmp_path):
    service = make_service(tmp_path, team_result())
    run = service.run_team("Герой заходить у покинуту дитячу лікарню.")
    service.save_scene(run, "Іваненко", confirmed=True)
    with pytest.raises(ValueError):
        service.save_scene(run, "Іваненко", confirmed=True)
    assert len(list((service.vault / "Inbox").glob("*.md"))) == 1


def test_rate_updates_journal(tmp_path):
    service = make_service(tmp_path, team_result())
    run = service.run_team("Герой заходить у покинуту дитячу лікарню.")
    service.rate(run.run_id, positive=True)
    assert service.history.get(run.run_id)["rating"] == 1
    assert service.history.summary()["positive_share"] == 1.0
