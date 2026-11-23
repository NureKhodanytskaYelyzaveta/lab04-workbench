"""Параметри бази знань. Значення читаються з .env, у коді лише типові."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class KBConfig:
    vault_path: Path                      # сховище Obsidian
    chroma_path: Path                     # каталог даних Chroma (PersistentClient)
    chroma_host: str | None = None        # якщо задано: HttpClient замість PersistentClient
    chroma_port: int = 8000
    collection: str = "obsidian-kb"       # 3-512 символів [a-zA-Z0-9._-]
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    chunk_chars: int = 1200               # верхня межа розміру фрагмента
    top_k: int = 4                        # скільки фрагментів повертати
    max_distance: float = 0.45            # поріг релевантності, калібрується


def load_config() -> KBConfig:
    vault = os.getenv("OBSIDIAN_VAULT")
    if not vault:
        raise RuntimeError("Задайте OBSIDIAN_VAULT у файлі .env")
    vault_path = Path(vault).expanduser().resolve()
    if not vault_path.is_dir():
        raise RuntimeError(f"Сховище не знайдено: {vault_path}")
    return KBConfig(
        vault_path=vault_path,
        chroma_path=Path(os.getenv("CHROMA_PATH", "./chroma_data")).expanduser().resolve(),
        chroma_host=os.getenv("CHROMA_HOST") or None,
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        collection=os.getenv("KB_COLLECTION", "obsidian-kb"),
        embed_model=os.getenv("EMBED_MODEL", "gemini-embedding-001"),
        embed_dim=int(os.getenv("EMBED_DIM", "768")),
        chunk_chars=int(os.getenv("KB_CHUNK_CHARS", "1200")),
        top_k=int(os.getenv("KB_TOP_K", "4")),
        max_distance=float(os.getenv("KB_MAX_DISTANCE", "0.45")),
    )
