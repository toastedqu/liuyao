from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.api.schemas import UsefulGodInput
from app.rules.models import Relative
from app.rules.models import UsefulGodChoice


@dataclass(frozen=True, slots=True)
class UsefulGodMapping:
    mode: Literal["world", "response", "relative"]
    relative: Relative | None
    source_ids: tuple[str, ...]
    description: str


_PARENT = UsefulGodMapping(
    "relative",
    Relative.PARENT,
    ("008_用神章:p0001",),
    "父母、师长、庇护之物、宅舍文书等取父母爻",
)
_OFFICIAL = UsefulGodMapping(
    "relative",
    Relative.OFFICIAL,
    ("008_用神章:p0002",),
    "丈夫、功名、官府、盗贼等取官鬼爻",
)
_SIBLING = UsefulGodMapping(
    "relative",
    Relative.SIBLING,
    ("008_用神章:p0003",),
    "兄弟姐妹及同辈亲属取兄弟爻",
)
_WEALTH = UsefulGodMapping(
    "relative",
    Relative.WEALTH,
    ("008_用神章:p0006",),
    "妻妾、下役、货财器物等取妻财爻",
)
_CHILD = UsefulGodMapping(
    "relative",
    Relative.CHILD,
    ("008_用神章:p0007",),
    "子女晚辈、医药、士卒、六畜等取子孙爻",
)

USEFUL_GOD_MAPPINGS: dict[UsefulGodInput, UsefulGodMapping] = {
    UsefulGodInput.WORLD: UsefulGodMapping(
        "world",
        None,
        ("031_各门类题头总注章:p0010",),
        "用户选择世爻为主事爻",
    ),
    UsefulGodInput.RESPONSE: UsefulGodMapping(
        "response",
        None,
        ("008_用神章:p0005",),
        "用户选择应爻为主事爻",
    ),
    UsefulGodInput.PARENT: _PARENT,
    UsefulGodInput.SIBLING: _SIBLING,
    UsefulGodInput.OFFICIAL: _OFFICIAL,
    UsefulGodInput.WEALTH: _WEALTH,
    UsefulGodInput.CHILD: _CHILD,
}


def build_useful_god_choice(
    *,
    question: str,
    useful_god: UsefulGodInput,
) -> UsefulGodChoice:
    mapping = USEFUL_GOD_MAPPINGS[useful_god]
    return UsefulGodChoice(
        target=question,
        mode=mapping.mode,
        useful_relative=mapping.relative,
        rationale=f"{mapping.description}；不由模型改选。",
        source_ids=mapping.source_ids,
    )
