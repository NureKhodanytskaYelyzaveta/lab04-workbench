"""Демонстраційний режим без ключа API: підмінні моделі й лексичні ембединги.

PYTHONPATH=. uv run streamlit run tests/demo_app.py
"""
import shutil
import tempfile
from pathlib import Path

import chromadb
import streamlit as st

from app.agent import build_workflow
from app.kb_assistant import build_kb_assistant
from kb.embedder import HashEmbedder
from kb.indexer import index_vault
from kb.store import KnowledgeStore
from kb.tools import KnowledgeTools
from tests.fixtures import APPROVE, AUDIO, AUDIO_M, DIRECTOR, GOOD, SCENE, VISUAL, VISUAL_M
from tests.scripted import ScriptedLlm, ToolCallingLlm
from workbench.service import WorkbenchService
from workbench.storage import HistoryStore

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def demo_service() -> WorkbenchService:
    tmp = Path(tempfile.mkdtemp())
    vault = tmp / "horror-handbook"
    shutil.copytree(ROOT / "tests" / "vault", vault)
    store = KnowledgeStore(HashEmbedder(), "demo_kb",
                           client=chromadb.PersistentClient(path=str(tmp / "chroma")))
    index_vault(vault, store)
    tools = KnowledgeTools(store, vault, top_k=3, max_distance=0.9)
    team = ScriptedLlm(model="demo", script={
        SCENE: [GOOD], AUDIO_M: [AUDIO], VISUAL_M: [VISUAL], DIRECTOR: [APPROVE]})

    class DemoKb(ToolCallingLlm):
        async def generate_content_async(self, llm_request, stream=False):
            last = llm_request.contents[-1].parts[0] if llm_request.contents else None
            if not self.calls and not (last and last.function_response):
                self.calls = [("search_knowledge", {"query": "крива страху правила"})]
            async for r in super().generate_content_async(llm_request, stream):
                yield r

    kb_model = DemoKb(model="demo", answer=(
        "Сцена починається спокійно: страх першого біта не вище 30, а після кульмінації "
        "потрібна розрядка [[Крива страху#Правила]]."))
    return WorkbenchService(build_workflow(team, kb_search=tools.search_knowledge),
                            build_kb_assistant(kb_model, tools),
                            HistoryStore(tmp / "history.db"), vault, "horror-handbook")


st.session_state.setdefault("service", demo_service())
exec((ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
