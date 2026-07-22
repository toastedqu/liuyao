from __future__ import annotations

import pytest

from app.api.schemas import UsefulGodInput
from app.divination.useful_god import build_useful_god_choice
from app.rules.models import Relative


@pytest.mark.parametrize(
    ("useful_god", "mode", "relative"),
    [
        (UsefulGodInput.WORLD, "world", None),
        (UsefulGodInput.RESPONSE, "response", None),
        (UsefulGodInput.PARENT, "relative", Relative.PARENT),
        (UsefulGodInput.SIBLING, "relative", Relative.SIBLING),
        (UsefulGodInput.OFFICIAL, "relative", Relative.OFFICIAL),
        (UsefulGodInput.WEALTH, "relative", Relative.WEALTH),
        (UsefulGodInput.CHILD, "relative", Relative.CHILD),
    ],
)
def test_user_selection_maps_to_useful_god_without_selecting_a_line(
    useful_god: UsefulGodInput,
    mode: str,
    relative: Relative | None,
) -> None:
    choice = build_useful_god_choice(
        question="我的恋爱关系会如何发展？",
        useful_god=useful_god,
    )

    assert choice.mode == mode
    assert choice.useful_relative is relative
    assert choice.target == "我的恋爱关系会如何发展？"
    assert not hasattr(choice, "preferred_line")
    assert choice.source_ids
