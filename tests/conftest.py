"""Фікстури: база знань на тестовому сховищі і сервіс із підмінними моделями."""
import shutil
from pathlib import Path

import chromadb
import pytest

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

VAULT_NAME = "horror-handbook"


@pytest.fixture
def vault(tmp_path) -> Path:
    target = tmp_path / "vault"
    shutil.copytree(Path(__file__).parent / "vault", target)
    return target


@pytest.fixture
def kb_tools(vault, tmp_path) -> KnowledgeTools:
    store = KnowledgeStore(HashEmbedder(), "test_kb",
                           client=chromadb.PersistentClient(path=str(tmp_path / "chroma")))
    index_vault(vault, store)
    return KnowledgeTools(store, vault, top_k=3, max_distance=0.9)


@pytest.fixture
def service(kb_tools, vault, tmp_path) -> WorkbenchService:
    team_model = ScriptedLlm(model="scripted", script={
        SCENE: [GOOD], AUDIO_M: [AUDIO], VISUAL_M: [VISUAL], DIRECTOR: [APPROVE]})
    kb_model = ToolCallingLlm(
        model="scripted", calls=[("search_knowledge", {"query": "крива страху правила"})],
        answer="Сцена починається спокійно, страх першого біта не вище 30 [[Крива страху#Правила]].")
    return WorkbenchService(
        team_agent=build_workflow(team_model, kb_search=kb_tools.search_knowledge),
        kb_agent=build_kb_assistant(kb_model, kb_tools),
        history=HistoryStore(tmp_path / "history.db"),
        vault=vault, vault_name=VAULT_NAME)
