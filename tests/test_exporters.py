"""Експортери артефактів етапу: без ADK, Chroma і мережі."""
import json

import pytest

from tests.fixtures import GOOD
from workbench.exporters import (fear_value, save_to_vault, slugify, to_scene_json,
                                 to_vault_note, to_yarn, yarn_node_title)

AUDIO = {"cues": [{"beat_id": "B1", "kind": "ambient", "description": "гул", "volume": 0.4}]}
VISUAL = {"effects": [{"beat_id": "B1", "effect": "vignette", "intensity": 0.5,
                       "description": "віньєтка"}]}


def test_scene_json_has_normalized_fear_curve():
    data = json.loads(to_scene_json(GOOD, AUDIO, VISUAL))
    assert data["schema"] == "horror-scene/1"
    assert data["fear_curve"] == [0.15, 0.4, 0.65, 0.85, 0.45]
    assert all(0 <= v <= 1 for v in data["fear_curve"])
    assert data["beats"][3]["technique"] == "reveal"
    assert data["audio_cues"] == AUDIO["cues"] and data["visual_effects"] == VISUAL["effects"]


def test_fear_value_clamps_and_tolerates_bad_input():
    assert fear_value({"fear_target": 150}) == 1.0
    assert fear_value({"fear_target": -5}) == 0.0
    assert fear_value({"fear_target": "x"}) == 0.0


def test_yarn_node_title_is_ascii():
    title = yarn_node_title("Дитяче відділення")
    assert title.startswith("Scene_") and title.isascii()
    assert all(ch.isalnum() or ch == "_" for ch in title)


def test_yarn_has_structure_and_escapes_syntax():
    scene = {**GOOD, "inner_voice_lines": ["Тут хтось є... {x} <<jump>>"]}
    text = to_yarn(scene)
    lines = text.splitlines()
    assert lines[0].startswith("title: Scene_") and "---" in lines and lines[-1] == "==="
    assert "Герой: Тут хтось є... (x) «jump»" in lines
    assert not any("{" in line or "<<" in line for line in lines[3:])


def test_vault_note_records_reviewer_and_blocks_frontmatter_injection():
    note = to_vault_note("# Сцена", "abc123", 'Іван"\nrole: admin')
    header = note.split("---")[1]
    assert 'approved_by: "Іван\' role: admin"' in header
    assert "\nrole: admin" not in header


def test_save_to_vault_writes_only_to_inbox_and_never_overwrites(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    first = save_to_vault(vault, "один", "Дитяче відділення")
    second = save_to_vault(vault, "два", "Дитяче відділення")
    assert first.parent.name == second.parent.name == "Inbox"
    assert first != second and second.name.endswith("(2).md")
    assert first.read_text(encoding="utf-8") == "один"


def test_save_to_vault_rejects_folder_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(ValueError):
        save_to_vault(vault, "x", "Сцена", folder="../outside")


def test_slugify_keeps_cyrillic_and_drops_path_characters():
    assert slugify("Сцена: ліфт / 2") == "Сцена ліфт 2"
    assert slugify("///") == "horror-scene"
