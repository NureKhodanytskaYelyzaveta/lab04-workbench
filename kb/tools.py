"""Дії агента над базою знань. Повертають рядки-спостереження."""
import re
import time
from collections.abc import Callable
from pathlib import Path

from .store import KnowledgeStore
from .vault import parse_note, resolve_note_path, strip_wikilinks

NOT_FOUND = "NOT_FOUND"
INBOX = "Inbox"
MAX_WRITE_CHARS = 5000

# Людина підтверджує запис: confirm(шлях, текст) -> True/False
ConfirmFn = Callable[[str, str], bool]


def _defang(text: str) -> str:
    """Дані з нотатки не повинні закривати або відкривати службові теги."""
    return re.sub(r"<(/?)(fragment|note)\b", r"<\\\1\2", text, flags=re.IGNORECASE)


def _attr(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ")


class KnowledgeTools:
    def __init__(self, store: KnowledgeStore, vault: Path, top_k: int = 4,
                 max_distance: float = 0.45, max_note_chars: int = 4000,
                 confirm: ConfirmFn | None = None):
        self.store, self.vault = store, vault
        self.top_k, self.max_distance = top_k, max_distance
        self.max_note_chars = max_note_chars
        self.confirm = confirm

    def search_knowledge(self, query: str, tag: str | None = None) -> str:
        """Семантичний пошук фрагментів нотаток, найближчих до запиту."""
        hits = self.store.search(query, self.top_k, tag)
        relevant = [h for h in hits if h.distance <= self.max_distance]
        if not relevant:
            best = f"{hits[0].distance:.3f}" if hits else "n/a"
            return (f"{NOT_FOUND}: no notes closer than {self.max_distance} "
                    f"for query '{query}' (best distance: {best}).")
        # Межі <fragment> відділяють дані з нотаток від інструкцій агента
        return "\n".join(
            f'<fragment source="[[{_attr(h.title)}#{_attr(h.heading.split(" > ")[-1])}]]" '
            f'path="{_attr(h.path)}" distance="{h.distance:.3f}">\n'
            f"{_defang(strip_wikilinks(h.text))}\n</fragment>"
            for h in relevant)

    def read_note(self, path: str) -> str:
        """Повний текст нотатки зі сховища (для деталей поза фрагментом)."""
        try:
            file = resolve_note_path(self.vault, path)
        except ValueError as exc:
            return f"ERROR: {exc}"
        except FileNotFoundError:
            return f"{NOT_FOUND}: note '{path}' does not exist."
        note = parse_note(self.vault, file)
        text = _defang(strip_wikilinks(note.body).strip())
        if len(text) > self.max_note_chars:
            text = text[:self.max_note_chars] + "\n[...truncated]"
        links = ", ".join(note.links) or "none"
        return (f'<note source="[[{_attr(note.title)}]]" path="{_attr(note.path)}" '
                f'tags="{_attr(", ".join(note.tags))}" links="{_attr(links)}">\n'
                f'{text}\n</note>')

    def write_note(self, path: str, content: str) -> str:
        """Створює НОВУ нотатку лише в Inbox/ і лише після підтвердження людини."""
        name = path.strip().replace("\\", "/")
        if not name.endswith(".md"):
            name += ".md"
        if not name.startswith(f"{INBOX}/"):
            name = f"{INBOX}/{name}"
        inbox = (self.vault / INBOX).resolve()
        target = (self.vault / name).resolve()
        if not target.is_relative_to(inbox) or target == inbox:
            return f"ERROR: notes can only be created inside {INBOX}/"
        if target.exists():
            return f"ERROR: note '{name}' already exists; overwriting is not allowed"
        if len(content) > MAX_WRITE_CHARS:
            return f"ERROR: note is longer than {MAX_WRITE_CHARS} characters"
        rel = target.relative_to(self.vault.resolve()).as_posix()
        if self.confirm is None or not self.confirm(rel, content):
            return f"DENIED: the human did not confirm creating '{rel}'."
        header = (f"---\ntags: [inbox]\nsource: \"agent draft, not verified\"\n"
                  f"updated: {time.strftime('%Y-%m-%d')}\n---\n\n")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(header + content.strip() + "\n", encoding="utf-8")
        return f"OK: note '{rel}' created."


def build_tools(confirm: ConfirmFn | None = None) -> KnowledgeTools:
    """Збирає робочі інструменти з параметрів .env."""
    from .config import load_config
    from .embedder import make_embedder
    from .store import make_client

    cfg = load_config()
    client = make_client(cfg.chroma_path, cfg.chroma_host, cfg.chroma_port)
    store = KnowledgeStore(make_embedder(cfg.embed_model, cfg.embed_dim),
                           cfg.collection, client=client)
    return KnowledgeTools(store, cfg.vault_path, cfg.top_k, cfg.max_distance,
                          confirm=confirm)
