"""Детерміновані вузли графа: перевірки і маршрутизація без LLM."""
import json

from google.adk import Context, Event

MAX_DRAFTS = 3  # скільки разів дизайнер сцени може переписати чернетку
MAX_REQUEST_CHARS = 2000
MIN_REQUEST_CHARS = 15
MIN_BEATS, MAX_BEATS = 4, 8
START_FEAR_MAX = 30   # сцена починається спокійно
PEAK_FEAR_MIN = 70    # є кульмінація
RELEASE_MIN_DROP = 15  # після піку є розрядка


def as_text(node_input) -> str:
    """Перше повідомлення графа надходить як types.Content, а не рядок."""
    if hasattr(node_input, "parts"):
        return "".join(p.text or "" for p in node_input.parts or [])
    return str(node_input or "")


def intake(ctx: Context, node_input) -> Event:
    """Перевіряє запит користувача і готує стан."""
    text = as_text(node_input).strip()
    ctx.state["drafts"] = 0
    ctx.state["feedback"] = ""
    ctx.state["scene_issues"] = []
    ctx.state["link_issues"] = []
    if len(text) < MIN_REQUEST_CHARS:
        return Event(route="reject", output="Опишіть сцену щонайменше одним реченням.")
    if len(text) > MAX_REQUEST_CHARS:
        return Event(route="reject",
                     output=f"Запит довший за {MAX_REQUEST_CHARS} символів; скоротіть його.")
    ctx.state["request"] = text
    return Event(route="ok", output=text)


def scene_issues(scene: dict) -> list[str]:
    """Формальні вимоги до сцени, які перевіряє код, а не модель."""
    issues = []
    beats = scene.get("beats") or []
    if not MIN_BEATS <= len(beats) <= MAX_BEATS:
        issues.append(f"Потрібно {MIN_BEATS}-{MAX_BEATS} бітів, отримано {len(beats)}.")
    ids = [b.get("id") for b in beats]
    if len(set(ids)) != len(ids):
        issues.append("Ідентифікатори бітів мають бути унікальними.")
    fears = []
    for b in beats:
        value = b.get("fear_target")
        if not isinstance(value, (int, float)) or not 0 <= value <= 100:
            issues.append(f"Біт {b.get('id')}: fear_target має бути числом від 0 до 100.")
        else:
            fears.append(value)
    if fears and len(fears) == len(beats):
        if fears[0] > START_FEAR_MAX:
            issues.append(f"Сцена має починатися спокійно: fear_target першого біта "
                          f"<= {START_FEAR_MAX}.")
        peak = max(fears)
        if peak < PEAK_FEAR_MIN:
            issues.append(f"Немає кульмінації: максимум страху {peak} < {PEAK_FEAR_MIN}.")
        else:
            after = fears[fears.index(peak) + 1:]
            if not after or min(after) > peak - RELEASE_MIN_DROP:
                issues.append(f"Після піку немає розрядки: потрібен біт щонайменше "
                              f"на {RELEASE_MIN_DROP} нижчий за пік.")
    for field in ("title", "setting", "player_goal"):
        if not str(scene.get(field, "")).strip():
            issues.append(f"Порожнє поле {field}.")
    return issues


def link_issues(scene: dict, audio: dict, visual: dict) -> list[str]:
    """Звірка планів звуку і візуалу зі сценою: посилання існують, межі, покриття."""
    issues = []
    ids = {b.get("id") for b in scene.get("beats") or []}
    covered = set()
    for c in audio.get("cues") or []:
        if c.get("beat_id") not in ids:
            issues.append(f"Звук посилається на неіснуючий біт {c.get('beat_id')}.")
        else:
            covered.add(c["beat_id"])
        vol = c.get("volume")
        if not isinstance(vol, (int, float)) or not 0 <= vol <= 1:
            issues.append(f"Гучність звуку біта {c.get('beat_id')} поза межами 0..1.")
    for e in visual.get("effects") or []:
        if e.get("beat_id") not in ids:
            issues.append(f"Візуальний ефект посилається на неіснуючий біт {e.get('beat_id')}.")
        else:
            covered.add(e["beat_id"])
        val = e.get("intensity")
        if not isinstance(val, (int, float)) or not 0 <= val <= 1:
            issues.append(f"Інтенсивність ефекту біта {e.get('beat_id')} поза межами 0..1.")
    for missing in sorted(ids - covered):
        issues.append(f"Біт {missing} не має ні звуку, ні візуального ефекту.")
    return issues


def scene_check(ctx: Context, node_input) -> Event:
    """Guardrail після дизайнера: невалідну сцену повертаємо без витрат на інших агентів."""
    ctx.state["drafts"] = ctx.state.get("drafts", 0) + 1
    issues = scene_issues(node_input or {})
    if issues and ctx.state["drafts"] < MAX_DRAFTS:
        ctx.state["feedback"] = "Виправ структуру сцени: " + " ".join(issues)
        return Event(route="fix", output=issues)
    ctx.state["scene_issues"] = issues  # на останній спробі лише фіксуємо
    return Event(route="ok", output=node_input)


def link_check(ctx: Context, node_input) -> Event:
    """Після JoinNode: плани звуку й візуалу узгоджені зі сценою, до директора."""
    issues = link_issues(ctx.state.get("scene") or {}, ctx.state.get("audio_plan") or {},
                         ctx.state.get("visual_plan") or {})
    if issues and ctx.state.get("drafts", 0) < MAX_DRAFTS:
        ctx.state["feedback"] = ("Плани звуку/візуалу не узгоджені зі сценою: "
                                 + " ".join(issues) + " Перелічи всі біти з id B1, B2, ...")
        return Event(route="fix", output=issues)
    ctx.state["link_issues"] = issues
    return Event(route="ok", output=node_input)


def gate(ctx: Context, node_input) -> Event:
    """Рішення директора + ліміт ітерацій -> куди йти далі."""
    verdict = node_input or {}
    if verdict.get("decision") == "APPROVE":
        ctx.state["stop_reason"] = "approved"
        return Event(route="publish", output=verdict)
    if ctx.state.get("drafts", 0) >= MAX_DRAFTS:
        ctx.state["stop_reason"] = "max_drafts"
        return Event(route="publish", output=verdict)
    ctx.state["feedback"] = "; ".join(verdict.get("comments", []))
    return Event(route="revise", output=verdict)


def fear_curve(scene: dict) -> list[float]:
    """Крива страху, нормалізована до 0..1 для FearLevelController у Unity."""
    return [round(b.get("fear_target", 0) / 100, 2) for b in scene.get("beats", [])]


def render_report(state: dict) -> str:
    """Збирає підсумковий Markdown зі стану сесії."""
    scene = state.get("scene") or {}
    audio = state.get("audio_plan") or {}
    visual = state.get("visual_plan") or {}
    verdict = state.get("verdict") or {}
    beats = scene.get("beats", [])
    lines = [
        f"# {scene.get('title', 'Сцена')}",
        "",
        f"**Локація:** {scene.get('setting', '')}",
        f"**Мета гравця:** {scene.get('player_goal', '')}",
        "",
        "## Біти і крива страху",
        *[f"- {b['id']} ({b['technique']}, страх {b['fear_target']}): {b['description']}"
          for b in beats],
        "",
        "Крива для FearLevelController (0..1): " + json.dumps(fear_curve(scene)),
        "",
        "## Звук",
        *[f"- {c['beat_id']} [{c['kind']}, {c['volume']}]: {c['description']}"
          for c in audio.get("cues", [])],
        "",
        "## Візуальні ефекти",
        *[f"- {e['beat_id']} [{e['effect']}, {e['intensity']}]: {e['description']}"
          for e in visual.get("effects", [])],
        "",
        "## Внутрішній голос (Yarn Spinner)",
        *[f"- {line}" for line in scene.get("inner_voice_lines", [])],
        "",
        "## Рішення",
        f"{verdict.get('decision', '?')} після {state.get('drafts', 0)} чернеток "
        f"(причина зупинки: {state.get('stop_reason', '?')}).",
    ]
    if verdict.get("decision") != "APPROVE" and verdict.get("comments"):
        lines += ["", "Невиконані зауваження:", *[f"- {c}" for c in verdict["comments"]]]
    leftovers = (state.get("scene_issues") or []) + (state.get("link_issues") or [])
    if leftovers:
        lines += ["", "Порушення, що лишилися:", *[f"- {i}" for i in leftovers]]
    return "\n".join(lines)


def publish(ctx: Context, node_input) -> Event:
    report = render_report(ctx.state.to_dict())
    ctx.state["report"] = report
    return Event(message=report, output=report)


def reject(ctx: Context, node_input) -> Event:
    return Event(message=f"Запит відхилено: {node_input}", output=None)
