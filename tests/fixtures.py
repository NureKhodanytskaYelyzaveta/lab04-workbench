"""Готові відповіді агентів для тестів."""
REQUEST = "Герой заходить у покинуту дитячу лікарню, де чути дитячий сміх."


def beat(i, fear, technique="buildup"):
    return {"id": f"B{i}", "description": f"Біт {i}", "technique": technique,
            "fear_target": fear}


GOOD = {
    "title": "Дитяче відділення", "setting": "Покинута лікарня вночі",
    "player_goal": "знайти вихід", "inner_voice_lines": ["Тут хтось є..."],
    "beats": [beat(1, 15), beat(2, 40), beat(3, 65), beat(4, 85, "reveal"),
              beat(5, 45, "release")],
}
AUDIO = {"cues": [{"beat_id": f"B{i}", "kind": "ambient", "description": "гул",
                   "volume": 0.4} for i in range(1, 6)]}
VISUAL = {"effects": [{"beat_id": f"B{i}", "effect": "vignette", "intensity": 0.5,
                       "description": "віньєтка"} for i in range(1, 6)]}
APPROVE = {"decision": "APPROVE", "comments": []}
REVISE = {"decision": "REVISE", "comments": ["більше невизначеності"]}

# унікальні фрагменти інструкцій агентів (маркери для ScriptedLlm)
SCENE, AUDIO_M, VISUAL_M, DIRECTOR = (
    "horror scene designer", "sound designer", "visual effects artist", "creative director")
