from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
)

from app.fact_display import fact_result_for_display
from app.fact_types import fact_type_label


class Element(StrEnum):
    WOOD = "木"
    FIRE = "火"
    EARTH = "土"
    METAL = "金"
    WATER = "水"


class Relative(StrEnum):
    PARENT = "父母"
    SIBLING = "兄弟"
    OFFICIAL = "官鬼"
    WEALTH = "妻财"
    CHILD = "子孙"


class Hexagram(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    lines: tuple[bool, bool, bool, bool, bool, bool] = Field(
        description="初爻至上爻；true 为阳，false 为阴"
    )
    lower_trigram: str
    upper_trigram: str
    palace: str
    palace_element: Element
    palace_sequence: int = Field(ge=1, le=8)
    palace_stage: Literal["本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"]
    world_line: int = Field(ge=1, le=6)
    response_line: int = Field(ge=1, le=6)
    is_six_clash: bool
    is_six_harmony: bool
    is_wandering_soul: bool
    is_returning_soul: bool


class HiddenSpirit(BaseModel):
    model_config = ConfigDict(frozen=True)

    stem: str
    branch: str
    element: Element
    relative: Relative
    source_hexagram: str


class ChangedLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_yang: bool
    stem: str
    branch: str
    element: Element
    relative: Relative


class ChartLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1, le=6)
    name: str
    raw_value: Literal[6, 7, 8, 9]
    is_yang: bool
    is_moving: bool
    spirit: str
    stem: str
    branch: str
    element: Element
    relative: Relative
    is_world: bool
    is_response: bool
    changed: ChangedLine | None = None
    hidden_spirit: HiddenSpirit | None = None


class ChartFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str = Field(description="内部稳定类型代码；对外 JSON 统一序列化为中文")
    line: int | None = None
    value: JsonValue
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    rule_source: str

    @field_validator("type")
    @classmethod
    def validate_type_has_label(cls, fact_type: str) -> str:
        fact_type_label(fact_type)
        return fact_type

    @field_serializer("type", when_used="json")
    def serialize_type(self, fact_type: str) -> str:
        return fact_type_label(fact_type)

    @field_serializer("value", when_used="json")
    def serialize_value(self, _value: JsonValue) -> JsonValue:
        return fact_result_for_display(self)


class Chart(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_order: Literal["初爻至上爻"] = "初爻至上爻"
    raw_lines: tuple[
        Literal[6, 7, 8, 9],
        Literal[6, 7, 8, 9],
        Literal[6, 7, 8, 9],
        Literal[6, 7, 8, 9],
        Literal[6, 7, 8, 9],
        Literal[6, 7, 8, 9],
    ]
    primary: Hexagram
    changed: Hexagram
    lines: tuple[ChartLine, ChartLine, ChartLine, ChartLine, ChartLine, ChartLine]
    facts: tuple[ChartFact, ...]
