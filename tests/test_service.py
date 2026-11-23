"""Сервіс з реальним графом ЛР 3, підмінними моделями й лексичними ембедингами (без мережі)."""
import pytest

from tests.fixtures import REQUEST


def test_team_uses_knowledge_base_context(service):
    events = []
    run = service.run_team(REQUEST, on_event=events.append)
    assert run.ok and run.scene["title"] == "Дитяче відділення"
    assert run.scene_json.startswith("{") and run.yarn.startswith("title: Scene_")
    assert run.result.state["kb_context"].startswith(("<fragment", "NOT_FOUND"))
    assert any(e["node"].startswith("retrieve_context") for e in events)
    assert service.history.get(run.run_id)["stop_reason"] == "approved"


def test_scene_designer_receives_kb_fragments(service):
    run = service.run_team("Крива страху сцени: спокійний початок, кульмінація і розрядка героя.")
    assert run.result.state["kb_context"].startswith("<fragment")
    assert run.kb_sources and run.kb_sources[0]["url"].startswith("obsidian://open")


def test_ask_returns_verified_sources(service):
    answer = service.ask("Як будувати криву страху?")
    labels = [s["label"] for s in answer.sources]
    assert answer.text.endswith("[[Крива страху#Правила]].")
    assert answer.invalid_citations == []
    assert any(label.startswith("Крива страху#") for label in labels)
    assert answer.sources[0]["url"].startswith("obsidian://open?vault=horror-handbook&file=")


def test_save_scene_requires_confirmation_and_reviewer(service):
    run = service.run_team(REQUEST)
    with pytest.raises(PermissionError):
        service.save_scene(run, "Іваненко", confirmed=False)
    with pytest.raises(ValueError):
        service.save_scene(run, reviewer=" ", confirmed=True)
    path = service.save_scene(run, reviewer="Іваненко", confirmed=True)
    assert path.parent.name == "Inbox"
    assert 'approved_by: "Іваненко"' in path.read_text(encoding="utf-8")


def test_team_without_kb_search_still_runs(service, kb_tools):
    from app.agent import build_workflow
    from tests.fixtures import APPROVE, AUDIO, AUDIO_M, DIRECTOR, GOOD, SCENE, VISUAL, VISUAL_M
    from tests.scripted import ScriptedLlm
    model = ScriptedLlm(model="scripted", script={
        SCENE: [GOOD], AUDIO_M: [AUDIO], VISUAL_M: [VISUAL], DIRECTOR: [APPROVE]})
    service.team_agent = build_workflow(model, kb_search=None)
    run = service.run_team(REQUEST)
    assert run.result.state["kb_context"].startswith("NOT_FOUND")
    assert run.ok


def test_merge_context_dedupes_fragments_and_falls_back_to_not_found():
    from app.context import merge_context
    a = '<fragment source="[[A#x]]" path="A.md" distance="0.1">\nтекст\n</fragment>'
    b = '<fragment source="[[B#y]]" path="B.md" distance="0.2">\nінше\n</fragment>'
    merged = merge_context([a + "\n" + b, a, "NOT_FOUND: nothing"])
    assert merged.count("<fragment ") == 2
    assert merge_context(["NOT_FOUND: x", "NOT_FOUND: y"]).startswith("NOT_FOUND")
