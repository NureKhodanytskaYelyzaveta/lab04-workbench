"""Сервісний шар: усе, що вміє робоче місце, без залежності від інтерфейсу.

Інтерфейс викликає лише методи WorkbenchService: ask, run_team, save_scene, rate
і читає service.history. Агенти, журнал і сховище передаються в конструктор,
тому тести підставляють підмінні моделі й тимчасові файли.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .exporters import save_to_vault, to_scene_json, to_vault_note, to_yarn
from .runner import OnEvent, RunResult, run_agent
from .storage import HistoryStore

SOURCE = re.compile(r'source="\[\[([^\]]+)\]\]" path="([^"]+)"')
CITATION = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class Answer:
    run_id: str
    text: str
    sources: list[dict]  # [{"label": "Крива страху#Правила", "path": "...", "url": "obsidian://..."}]
    invalid_citations: list[str]
    result: RunResult

    @property
    def linked_text(self) -> str:
        """[[Нотатка#Розділ]] у відповіді -> посилання, що відкриває нотатку в Obsidian."""
        urls = {s["label"]: s["url"] for s in self.sources}
        return CITATION.sub(
            lambda m: f"[{m.group(1)}]({urls[m.group(1)]})" if m.group(1) in urls else m.group(0),
            self.text)


@dataclass
class TeamRun:
    run_id: str
    scene: dict
    audio: dict
    visual: dict
    report: str            # scene.md
    scene_json: str        # scene.json
    yarn: str              # scene.yarn
    kb_sources: list[dict]  # фрагменти бази знань, що потрапили до дизайнера сцени
    result: RunResult
    stop_reason: str = ""

    @property
    def ok(self) -> bool:
        """False, якщо запит відхилено і сцени немає."""
        return bool(self.scene)


class WorkbenchService:
    def __init__(self, team_agent, kb_agent, history: HistoryStore,
                 vault: Path | None = None, vault_name: str = "", run_fn=run_agent):
        self.team_agent, self.kb_agent = team_agent, kb_agent
        self.history, self.vault, self.vault_name = history, vault, vault_name
        self._run = run_fn

    def obsidian_url(self, path: str) -> str:
        """URI, що відкриває нотатку в застосунку Obsidian."""
        return f"obsidian://open?vault={quote(self.vault_name)}&file={quote(path)}"

    def _sources(self, found: dict[str, str]) -> list[dict]:
        return [{"label": label, "path": path, "url": self.obsidian_url(path)}
                for label, path in found.items()]

    # UC1: питання до бази знань
    def ask(self, question: str, on_event: OnEvent | None = None) -> Answer:
        result = self._run(self.kb_agent, question, on_event)
        found: dict[str, str] = {}
        for output in result.tool_outputs:
            for label, path in SOURCE.findall(output):
                found[label] = path
        cited = CITATION.findall(result.final_text)
        known_notes = {label.split("#")[0] for label in found}
        invalid = sorted({c for c in cited
                          if c not in found and c.split("#")[0] not in known_notes})
        run_id = self.history.add("ask", question, result.final_text,
                                  sum(result.llm_calls.values()), result.tokens, result.seconds,
                                  details={"sources": list(found), "invalid": invalid})
        return Answer(run_id, result.final_text, self._sources(found), invalid, result)

    # UC2: запуск команди агентів
    def run_team(self, request: str, on_event: OnEvent | None = None) -> TeamRun:
        result = self._run(self.team_agent, request, on_event)
        state = result.state
        scene = state.get("scene") or {}
        audio = state.get("audio_plan") or {}
        visual = state.get("visual_plan") or {}
        report = state.get("report") or result.final_text
        stop_reason = state.get("stop_reason") or ("" if scene else "rejected")
        kb_found = {label: path
                    for label, path in SOURCE.findall(str(state.get("kb_context", "")))}
        run_id = self.history.add(
            "team", request, report, sum(result.llm_calls.values()), result.tokens,
            result.seconds, stop_reason,
            details={"drafts": state.get("drafts"), "llm_calls": result.llm_calls,
                     "kb_sources": list(kb_found)})
        return TeamRun(
            run_id=run_id, scene=scene, audio=audio, visual=visual, report=report,
            scene_json=to_scene_json(scene, audio, visual) if scene else "",
            yarn=to_yarn(scene) if scene else "",
            kb_sources=self._sources(kb_found), result=result, stop_reason=stop_reason)

    # UC4: людина в циклі
    def save_scene(self, run: TeamRun, reviewer: str, confirmed: bool = False) -> Path:
        """Запис у базу знань лише після явного підтвердження і з іменем рецензента."""
        if not confirmed:
            raise PermissionError("the human has not confirmed the review")
        if not reviewer.strip():
            raise ValueError("reviewer name is required")
        if not self.vault:
            raise RuntimeError("vault is not configured")
        if not run.ok:
            raise ValueError("there is no scene to save")
        record = self.history.get(run.run_id)
        if record and record["saved_path"]:
            raise ValueError("this run has already been saved")
        note = to_vault_note(run.report, run.run_id, reviewer.strip())
        path = save_to_vault(self.vault, note, run.scene.get("title", "Horror scene"))
        self.history.mark_saved(run.run_id, str(path))
        return path

    # UC5: оцінка результату
    def rate(self, run_id: str, positive: bool) -> None:
        self.history.rate(run_id, int(positive))


def build_service() -> WorkbenchService:
    """Робоча конфігурація з .env: Gemini, Chroma, сховище Obsidian, SQLite."""
    import os

    from dotenv import load_dotenv

    load_dotenv()  # до імпорту ADK-модулів, щоб GEMINI_MODEL і ключ уже були в оточенні
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        raise RuntimeError("Задайте GEMINI_API_KEY у файлі .env")

    from app.agent import build_workflow, gemini
    from app.kb_assistant import build_kb_assistant
    from kb.tools import build_tools

    tools = build_tools()
    team = build_workflow(gemini(), kb_search=tools.search_knowledge)
    assistant = build_kb_assistant(gemini(), tools)
    history = HistoryStore(os.getenv("WORKBENCH_DB", "workbench.db"))
    return WorkbenchService(team, assistant, history, tools.vault,
                            os.getenv("OBSIDIAN_VAULT_NAME", tools.vault.name))
