from __future__ import annotations

import re

import pytest

from app.fact_types import (
    CHART_FACT_TYPE_LABELS,
    FACT_TYPE_LABELS,
    RULE_FACT_TYPE_LABELS,
    fact_type_label,
)
from app.rules.registry import RULES


def test_every_registered_fact_type_has_a_unique_chinese_label() -> None:
    registered_rule_types = {
        fact_type
        for rule in RULES
        for fact_type in rule.fact_types
    }

    assert set(RULE_FACT_TYPE_LABELS) == registered_rule_types
    assert set(FACT_TYPE_LABELS) == (
        set(CHART_FACT_TYPE_LABELS) | registered_rule_types
    )
    assert len(set(FACT_TYPE_LABELS.values())) == len(FACT_TYPE_LABELS)
    assert all(
        re.search(r"[\u4e00-\u9fff]", label)
        and re.search(r"[A-Za-z_]", label) is None
        for label in FACT_TYPE_LABELS.values()
    )


def test_fact_type_label_is_idempotent_and_rejects_unknown_types() -> None:
    assert fact_type_label("MONTH_BREAK") == "月破"
    assert fact_type_label("月破") == "月破"

    with pytest.raises(ValueError, match="事实类型未登记中文名称"):
        fact_type_label("UNREGISTERED_FACT")
