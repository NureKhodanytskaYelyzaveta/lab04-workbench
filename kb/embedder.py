"""Моделі ембедингів: Gemini для роботи, HashEmbedder для тестів без мережі."""
import hashlib
import math
import re
import time
from collections import deque
from typing import Protocol


class Embedder(Protocol):
    name: str                      # потрапляє в метадані колекції
    calls: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class _Throttle:
    """Не більше per_minute текстів за 60 с (ліміт безкоштовного рівня Gemini API
    рахується за текстами, а не за викликами)."""

    def __init__(self, per_minute: int = 90):
        self.per_minute = per_minute
        self.events: deque[tuple[float, int]] = deque()

    def wait(self, n: int) -> None:
        while True:
            now = time.monotonic()
            while self.events and now - self.events[0][0] >= 60:
                self.events.popleft()
            used = sum(c for _, c in self.events)
            if not self.events or used + n <= self.per_minute:
                break
            time.sleep(60 - (now - self.events[0][0]) + 0.5)
        self.events.append((time.monotonic(), n))


class GeminiEmbedder:
    """gemini-embedding-001: різні task_type для документів і запитів."""

    def __init__(self, model: str = "gemini-embedding-001", dim: int = 768,
                 batch_size: int = 50):
        from google import genai
        self.model, self.dim, self.batch_size = model, dim, batch_size
        self.name = f"{model}:{dim}"
        self.calls = 0                       # лічильник запитів до API
        self._client = genai.Client()        # GEMINI_API_KEY з оточення
        self._throttle = _Throttle()

    def _embed(self, texts: list[str], task: str | None) -> list[list[float]]:
        from google.genai import types
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            config = types.EmbedContentConfig(
                task_type=task, output_dimensionality=self.dim)
            for attempt in (1, 2, 3):
                self._throttle.wait(len(batch))
                self.calls += 1
                try:
                    response = self._client.models.embed_content(
                        model=self.model, contents=batch, config=config)
                    break
                except Exception as exc:
                    if "429" not in str(exc) or attempt == 3:
                        raise
                    time.sleep(35)               # квота на хвилину: чекаємо й повторюємо
            got = [list(e.values) for e in response.embeddings]
            if len(got) != len(batch):
                raise ValueError(f"{self.model} returned {len(got)} embeddings "
                                 f"for {len(batch)} texts; use batch_size=1")
            if got and len(got[0]) != self.dim:
                raise ValueError(f"{self.model} returned {len(got[0])} dims; "
                                 f"set EMBED_DIM={len(got[0])}")
            vectors += [_normalize(v) for v in got]
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


class PrefixGeminiEmbedder(GeminiEmbedder):
    """gemini-embedding-2: параметра task_type немає, тип задачі задають
    префіксом у тексті (формат перевірте в документації моделі)."""

    def __init__(self, model: str = "gemini-embedding-2", dim: int = 768):
        super().__init__(model, dim, batch_size=1)   # модель повертає 1 вектор на виклик

    DOC_PREFIX = "title: none | text: "
    QUERY_PREFIX = "task: search result | query: "

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([self.DOC_PREFIX + t for t in texts], None)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self.QUERY_PREFIX + text], None)[0]


class ChromaDefaultEmbedder:
    """Стандартна модель Chroma all-MiniLM-L6-v2 (384 виміри, переважно англійська).
    Для порівняння моделей (просунутий крок 13)."""

    def __init__(self):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        self._fn = DefaultEmbeddingFunction()
        self.name = "chroma-all-MiniLM-L6-v2:384"
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [list(map(float, v)) for v in self._fn(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class HashEmbedder:
    """Детерміновані «ембединги» з триграм символів. Лише для тестів:
    відображають лексичну, а не смислову схожість."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.name = f"hash-trigram:{dim}"
        self.calls = 0

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            padded = f"#{word}#"
            for i in range(len(padded) - 2):
                digest = hashlib.md5(padded[i:i + 3].encode()).digest()
                vector[int.from_bytes(digest[:4], "little") % self.dim] += 1.0
        return _normalize(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return self._vector(text)


def make_embedder(model: str, dim: int) -> Embedder:
    """Вибір моделі за назвою з .env (EMBED_MODEL)."""
    if model == "chroma-default":
        return ChromaDefaultEmbedder()
    if model.startswith("gemini-embedding-2"):
        return PrefixGeminiEmbedder(model, dim)
    return GeminiEmbedder(model, dim)
