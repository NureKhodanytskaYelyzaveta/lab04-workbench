"""Перетворення результатів команди на артефакти етапу «Проєктування».

Артефакти використовує розробник Unity на наступному етапі (конструювання):
  * scene.json  — крива страху 0..1, звук і ефекти, прив'язані до бітів, для
                  FearLevelController та інших скриптів сцени;
  * scene.yarn  — репліки внутрішнього голосу для Yarn Spinner;
  * scene.md    — проєктна документація сцени (звіт команди).
Модуль не залежить ні від ADK, ні від Streamlit.
"""
import json
import re
from datetime import date
from pathlib import Path

SCHEMA_VERSION = "horror-scene/1"

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "",
    "ю": "iu", "я": "ia", "'": "", "’": "", "ʼ": "",
}


def fear_value(beat: dict) -> float:
    """fear_target 0..100 -> 0..1 для FearLevelController."""
    value = beat.get("fear_target", 0)
    value = value if isinstance(value, (int, float)) else 0
    return round(max(0, min(100, value)) / 100, 2)


def to_scene_json(scene: dict, audio: dict | None = None, visual: dict | None = None) -> str:
    """JSON-специфікація сцени для імпорту в Unity."""
    beats = scene.get("beats") or []
    data = {
        "schema": SCHEMA_VERSION,
        "title": scene.get("title", ""),
        "setting": scene.get("setting", ""),
        "player_goal": scene.get("player_goal", ""),
        "fear_curve": [fear_value(b) for b in beats],
        "beats": [{"id": b.get("id"), "description": b.get("description", ""),
                   "technique": b.get("technique"), "fear": fear_value(b)} for b in beats],
        "audio_cues": (audio or {}).get("cues", []),
        "visual_effects": (visual or {}).get("effects", []),
        "inner_voice_lines": scene.get("inner_voice_lines", []),
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def transliterate(text: str) -> str:
    return "".join(_TRANSLIT.get(ch, _TRANSLIT.get(ch.lower(), ch)) for ch in text)


def yarn_node_title(title: str) -> str:
    """Назва вузла Yarn Spinner: лише літери ASCII, цифри і підкреслення."""
    ascii_title = re.sub(r"[^A-Za-z0-9]+", "_", transliterate(title)).strip("_")
    return "Scene_" + (ascii_title[:50] or "Untitled")


def _yarn_line(text: str) -> str:
    """У Yarn { } — вирази, << >> — команди, // — коментар: у репліці їх прибираємо."""
    clean = " ".join(str(text).split())
    clean = clean.replace("{", "(").replace("}", ")").replace("<<", "«").replace(">>", "»")
    clean = clean.replace("//", "/ /")
    return clean.lstrip("-#") .strip()


def to_yarn(scene: dict, speaker: str = "Герой") -> str:
    """Вузол .yarn із репліками внутрішнього голосу; біти й страх — у коментарях."""
    lines = [f"title: {yarn_node_title(scene.get('title', ''))}", "tags: horror generated",
             "---", f"// Сцена: {_yarn_line(scene.get('title', ''))}"]
    for b in scene.get("beats") or []:
        lines.append(f"// {b.get('id')} fear={fear_value(b)}: "
                     f"{_yarn_line(b.get('description', ''))}")
    for text in scene.get("inner_voice_lines") or []:
        line = _yarn_line(text)
        if line:
            lines.append(f"{speaker}: {line}")
    lines.append("===")
    return "\n".join(lines) + "\n"


def slugify(title: str) -> str:
    """Безпечне ім'я файла: літери (зокрема кирилиця), цифри, пробіли, дефіси."""
    cleaned = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", cleaned)[:80] or "horror-scene"


def to_vault_note(report: str, run_id: str, reviewer: str) -> str:
    """Нотатка для сховища: YAML-властивості + звіт. Ім'я рецензента фіксується."""
    safe_reviewer = " ".join(reviewer.split()).replace('"', "'")
    return (f"---\ntags: [horror-scene, generated, approved]\n"
            f"source: \"workbench run {run_id}\"\n"
            f"approved_by: \"{safe_reviewer}\"\nupdated: {date.today().isoformat()}\n---\n"
            f"{report}\n")


def save_to_vault(vault: Path, note_text: str, title: str, folder: str = "Inbox") -> Path:
    """Пише нотатку лише в папку Inbox сховища і ніколи не перезаписує наявну."""
    target_dir = (vault / folder).resolve()
    if not target_dir.is_relative_to(vault.resolve()):
        raise ValueError("folder outside the vault")
    target_dir.mkdir(parents=True, exist_ok=True)
    base = slugify(title)
    path, n = target_dir / f"{base}.md", 2
    while path.exists():
        path, n = target_dir / f"{base} ({n}).md", n + 1
    path.write_text(note_text, encoding="utf-8")
    return path
