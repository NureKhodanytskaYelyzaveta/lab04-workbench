"""Збирання контексту з бази знань для дизайнера сцени (без залежності від ADK).

Опис сцени — довгий наративний текст, і за порогом KB_MAX_DISTANCE, відкаліброваним
для коротких запитів, він часто нічого не знаходить. Тому, окрім самого запиту,
робимо кілька коротких запитів про правила проєкту й об'єднуємо знайдені фрагменти.
"""
import re
from collections.abc import Callable

# Короткі запити про правила проєкту; підлаштуйте під теми у вашому сховищі
CONTEXT_QUERIES = (
    "шкала страху",
    "звук і візуальні ефекти страху",
    "атмосфера психологічного горору",
)
MAX_FRAGMENTS = 6
_FRAGMENT_START = re.compile(r"(?=<fragment )")


def merge_context(results: list[str], limit: int = MAX_FRAGMENTS) -> str:
    """Об'єднує відповіді пошуку: унікальні <fragment>, не більше limit; інакше NOT_FOUND."""
    seen: set[str] = set()
    blocks: list[str] = []
    for result in results:
        for block in _FRAGMENT_START.split(result):
            block = block.strip()
            if block.startswith("<fragment ") and block not in seen:
                seen.add(block)
                blocks.append(block)
    if not blocks:
        return next((r for r in results if r), "NOT_FOUND: no knowledge base fragments")
    return "\n".join(blocks[:limit])


def gather_context(kb_search: Callable[[str], str], request: str,
                   queries: tuple[str, ...] = CONTEXT_QUERIES) -> str:
    """Пошук за описом сцени і за короткими запитами про правила проєкту."""
    return merge_context([kb_search(request), *(kb_search(q) for q in queries)])
