"""Команда горор-сцени (ЛР 3) + вузол контексту з бази знань (ЛР 2).

Граф відрізняється від ЛР 3 одним вузлом: retrieve_context стоїть між intake і
scene_designer та кладе правила проєкту з бази знань у стан під ключем kb_context.
"""
import os
from collections.abc import Callable

from google.adk import Context, Workflow
from google.adk.models import Gemini
from google.adk.models.base_llm import BaseLlm
from google.adk.workflow import JoinNode
from google.genai import types

from .agents import build_agents
from .context import gather_context
from .nodes import gate, intake, link_check, publish, reject, scene_check

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

KbSearch = Callable[[str], str]


def build_workflow(model: BaseLlm | str, kb_search: KbSearch | None = None) -> Workflow:
    a = build_agents(model)
    plans = JoinNode(name="plans")  # чекає на обидві паралельні гілки

    def retrieve_context(ctx: Context, node_input):
        """Детермінований RAG-крок: правила проєкту з бази знань до дизайнера сцени."""
        request = ctx.state.get("request", "")
        if kb_search is None:
            ctx.state["kb_context"] = "NOT_FOUND: no knowledge base"
        else:
            try:
                ctx.state["kb_context"] = gather_context(kb_search, request)
            except Exception as exc:  # збій ембедингів чи Chroma не має зупиняти команду
                ctx.state["kb_context"] = f"NOT_FOUND: knowledge base error ({type(exc).__name__})"
        return node_input

    return Workflow(
        name="horror_team",
        max_concurrency=2,  # не більше двох агентів одночасно
        edges=[
            ("START", intake),
            (intake, {"ok": retrieve_context, "reject": reject}),
            (retrieve_context, a["scene"]),
            (a["scene"], scene_check),
            (scene_check, {"ok": (a["audio"], a["visual"]), "fix": a["scene"]}),
            (a["audio"], plans),
            (a["visual"], plans),
            (plans, link_check),
            (link_check, {"ok": a["director"], "fix": a["scene"]}),
            (a["director"], gate),
            (gate, {"revise": a["scene"], "publish": publish}),
        ],
    )


def gemini() -> Gemini:
    """Модель з .env: змінну читаємо під час виклику, а не під час імпорту модуля."""
    return Gemini(model=os.getenv("GEMINI_MODEL", MODEL),
                  retry_options=types.HttpRetryOptions(attempts=6))
