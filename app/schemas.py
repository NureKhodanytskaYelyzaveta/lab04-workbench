"""Контракти даних між агентами: кожен агент повертає JSON за схемою Pydantic.

Числові межі (fear_target 0-100, volume/intensity 0-1) свідомо перевіряє код
(app/nodes.py), а не Pydantic: помилка валідації схеми обриває запуск, а
детермінований вузол повертає чернетку автору з конкретним зауваженням.
"""
from typing import Literal

from pydantic import BaseModel, Field

Technique = Literal["buildup", "false_calm", "jump_scare", "ambiguity",
                    "isolation", "sound_only", "reveal", "release"]
AudioKind = Literal["ambient", "stinger", "heartbeat", "whisper", "silence"]
VisualEffectName = Literal["vignette", "light_flicker", "chromatic_aberration",
                           "camera_shake", "fog", "ui_pulse"]


class Beat(BaseModel):
    id: str = Field(description="Unique beat id in order: B1, B2, B3, ...")
    description: str = Field(description="What happens in this beat, 1-2 sentences")
    technique: Technique = Field(description="Main horror technique of the beat")
    fear_target: int = Field(
        description="Target player fear level 0-100 at the end of the beat")


class SceneDesign(BaseModel):
    title: str = Field(description="Short title of the scene")
    setting: str = Field(description="Location, time and atmosphere in 1-2 sentences")
    player_goal: str = Field(description="What the player tries to do in the scene")
    beats: list[Beat] = Field(description="4-8 beats in chronological order")
    inner_voice_lines: list[str] = Field(
        description="2-4 short lines of the hero's inner voice for Yarn Spinner dialogue")


class AudioCue(BaseModel):
    beat_id: str = Field(description="Id of an existing beat, e.g. B2")
    kind: AudioKind = Field(description="Type of sound")
    description: str = Field(description="Concrete sound: source, character, timing")
    volume: float = Field(description="Relative loudness from 0.0 to 1.0")


class AudioPlan(BaseModel):
    cues: list[AudioCue] = Field(description="Sound cues bound to beats")


class VisualEffect(BaseModel):
    beat_id: str = Field(description="Id of an existing beat, e.g. B2")
    effect: VisualEffectName = Field(description="Screen or lighting effect")
    intensity: float = Field(description="Effect strength from 0.0 to 1.0")
    description: str = Field(description="How the effect behaves in this beat")


class VisualPlan(BaseModel):
    effects: list[VisualEffect] = Field(description="Visual effects bound to beats")


class Verdict(BaseModel):
    decision: Literal["APPROVE", "REVISE"]
    comments: list[str] = Field(description="Specific changes the scene designer must make")
