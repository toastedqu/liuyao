from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_divination_service
from app.api.schemas import DivinationRequest
from app.config import Settings
from app.divination.service import DivinationService, DivinationValidationError
from app.fact_types import FACT_TYPE_LABELS
from app.knowledge.ingest import build_database
from app.llm.base import Message
from app.llm.schemas import (
    CaseAnalysis,
    CaseComparison,
    DivinationConclusion,
    Judgement,
    MonthDayAnalysis,
    MovingLinesAnalysis,
    OverallConclusion,
    QuestionCategory,
    QuestionApplication,
    RisksAndUncertainties,
    SourceCitation,
    SpecialPatternsAnalysis,
    TimingSelection,
    UsefulGodAnalysis,
)
from app.main import app


ROOT = Path(__file__).resolve().parents[2]
CASE_ID = "081_囤买卖货章:example0003"
CASE_QUESTION_ID = f"{CASE_ID}:question"
CASE_JUDGEMENT_ID = f"{CASE_ID}:judgement"


class SequenceProvider:
    def __init__(self, responses: list[Any]):
        self.responses = list(responses)
        self.calls: list[list[Message]] = []
        self.schemas: list[type] = []

    async def generate_structured(
        self,
        messages: list[Message],
        response_schema: type[DivinationConclusion],
    ) -> Any:
        self.calls.append(messages)
        self.schemas.append(response_schema)
        return self.responses.pop(0)


def request_payload(
    *,
    question: str = "本次求财是否可成？",
    lines: list[int] | None = None,
    useful_god: str = "妻财",
) -> dict:
    return {
        "question": question,
        "useful_god": useful_god,
        "calendar": {
            "year": 2026,
            "month": 7,
            "day": 17,
            "hour": 9,
            "timezone": "Asia/Shanghai",
        },
        "lines": lines or [6, 7, 8, 7, 7, 7],
    }


def assert_fact_values_are_localized(facts: list[dict[str, Any]]) -> None:
    for fact in facts:
        rendered = re.sub(
            r"fact-\S+",
            "",
            json.dumps(fact["value"], ensure_ascii=False),
        )
        assert re.search(r"[A-Za-z]", rendered) is None


def question_category(
    category: str = "求财",
    perspective: str = "自占",
) -> QuestionCategory:
    return QuestionCategory(category=category, perspective=perspective)


def conclusion(
    *,
    valid_source: bool = True,
    include_case: bool = True,
) -> DivinationConclusion:
    citation = (
        SourceCitation(
            source_id="008_用神章:p0006",
            quote="凡我驱使之人，皆以财爻为用神。",
        )
        if valid_source
        else SourceCitation(source_id="999_伪造章:p0001", quote="伪造原文")
    )
    judgement = Judgement(
        statement="日辰比扶用神，本次求财有成事基础。",
        fact_ids=["fact-day-relation-l5"],
        citations=[citation],
    )
    return DivinationConclusion(
        overall=OverallConclusion(
            outlook="吉",
            summary="本次求财有利",
            judgements=[judgement],
        ),
        question_application=QuestionApplication(
            focus="本次所问求财能否办成",
            favorable=[
                Judgement(
                    statement="日辰比扶用神，落实到本问为求财有助力。",
                    fact_ids=["fact-day-relation-l5"],
                )
            ],
            adverse=[],
            synthesis=Judgement(
                statement="本卦只有利主证，本次求财可按有利方向判断。",
                fact_ids=["fact-day-relation-l5"],
            ),
        ),
        case_analysis=CaseAnalysis(
            comparisons=[
                CaseComparison(
                    example_id=CASE_ID,
                    role="reference_only",
                    similarities=Judgement(
                        statement="本卦与原例同属求财问题，可比较财事成败。",
                        fact_ids=["fact-primary-hexagram"],
                        citations=[
                            SourceCitation(
                                source_id=CASE_QUESTION_ID,
                                quote="占买台连纸有利否",
                            )
                        ],
                    ),
                    differences=Judgement(
                        statement="本卦卦象并非原例复之颐，不能直接照搬结论。",
                        fact_ids=["fact-primary-hexagram"],
                        citations=[
                            SourceCitation(
                                source_id=CASE_QUESTION_ID,
                                quote="复之颐",
                            )
                        ],
                    ),
                    application=Judgement(
                        statement="原例把财爻旺衰落实为囤货获利时机；本问只迁移其判断方法。",
                        fact_ids=["fact-primary-hexagram"],
                        citations=[
                            SourceCitation(
                                source_id=CASE_JUDGEMENT_ID,
                                quote="秋冬必长，有纸多收",
                            )
                        ],
                    ),
                )
            ]
            if include_case
            else []
        ),
        useful_god=UsefulGodAnalysis(useful_god="妻财", judgements=[]),
        month_day=MonthDayAnalysis(judgements=[]),
        moving_lines=MovingLinesAnalysis(judgements=[]),
        special_patterns=SpecialPatternsAnalysis(patterns=[]),
        timing=TimingSelection(
            candidate_ids=[],
            judgements=[],
            insufficient_evidence=True,
        ),
        risks=RisksAndUncertainties(items=[]),
    )


@pytest.fixture(scope="module")
def knowledge_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("integration-kb") / "knowledge.sqlite3"
    stats = build_database(
        ROOT / "zengshan_buyi",
        path,
        repo_root=ROOT,
    )
    assert stats.complete
    return path


def service(
    knowledge_db: Path,
    provider: SequenceProvider,
) -> DivinationService:
    settings = Settings(
        _env_file=None,
        KNOWLEDGE_DB_PATH=knowledge_db,
        LLM_PROVIDER="openai",
    )
    return DivinationService(
        settings=settings,
        repo_root=ROOT,
        provider=provider,
    )


@pytest.fixture
def override_cleanup() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def test_chart_api_is_fully_deterministic_without_llm_configuration() -> None:
    payload = request_payload(lines=[7, 8, 6, 9, 7, 8])
    payload.pop("useful_god")
    response = TestClient(app).post(
        "/api/v1/chart",
        json=payload,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_summary"]["line_order"] == "初爻至上爻"
    assert payload["calendar"]["month_pillar"]["ganzhi"]["branch"] == "未"
    assert payload["calendar"]["day_pillar"]["ganzhi"] == {
        "stem": "壬",
        "branch": "辰",
    }
    assert payload["primary_hexagram"]["name"] == "泽雷随"
    assert payload["changed_hexagram"]["name"] == "水火既济"
    assert [line["raw_value"] for line in payload["lines"]] == [7, 8, 6, 9, 7, 8]
    assert payload["input_summary"]["category"] is None
    assert payload["useful_god"] is None
    assert payload["timing_candidates"] == []
    assert payload["facts"]
    fact_types = {fact["type"] for fact in payload["facts"]}
    assert {"主卦", "动爻", "静爻", "本爻四时旺衰"} <= fact_types
    assert fact_types <= set(FACT_TYPE_LABELS.values())
    relation = next(
        fact
        for fact in payload["facts"]
        if fact["type"] == "爻间五行生克"
        and fact["related_lines"] == [1, 2]
    )
    assert "初爻" in relation["value"]
    assert "二爻" in relation["value"]
    assert "实际发生作用" not in relation["value"]
    assert_fact_values_are_localized(payload["facts"])


@pytest.mark.asyncio
async def test_full_pipeline_retries_invalid_citation_once(knowledge_db: Path) -> None:
    provider = SequenceProvider(
        [
            question_category(),
            conclusion(valid_source=False),
            conclusion(valid_source=True),
        ]
    )
    divination = service(knowledge_db, provider)

    response = await divination.divine(
        DivinationRequest.model_validate(request_payload())
    )

    assert response.interpretation.overall.outlook == "吉"
    assert len(provider.calls) == 3
    assert provider.schemas == [
        QuestionCategory,
        DivinationConclusion,
        DivinationConclusion,
    ]
    assert "上一次的结构化结果未通过校验" in provider.calls[2][-1].content
    assert response.sources
    assert response.case_evidence
    assert len(response.case_evidence) == 3
    assert response.case_evidence[0].judgement.content_type.value == "example_judgement"
    assert all(not source.is_editorial for source in response.sources)
    assert any(source.source_id == "008_用神章:p0006" for source in response.sources)


@pytest.mark.asyncio
async def test_full_pipeline_corrects_false_adverse_outlook(
    knowledge_db: Path,
) -> None:
    false_adverse = conclusion()
    false_adverse.overall.outlook = "凶"
    false_adverse.overall.summary = "受参考卦例影响而误判为凶"
    false_adverse.overall.judgements[0].fact_ids = ["fact-primary-hexagram"]
    false_adverse.question_application.favorable = []
    false_adverse.question_application.adverse = [
        Judgement(
            statement="误把普通卦名当成不利证据。",
            fact_ids=["fact-primary-hexagram"],
        )
    ]
    false_adverse.question_application.synthesis.fact_ids = [
        "fact-primary-hexagram"
    ]
    provider = SequenceProvider(
        [
            question_category(),
            false_adverse,
            conclusion(),
        ]
    )
    divination = service(knowledge_db, provider)

    response = await divination.divine(
        DivinationRequest.model_validate(request_payload())
    )

    assert response.interpretation.overall.outlook == "吉"
    assert len(provider.calls) == 3
    correction_prompt = provider.calls[2][-1].content
    assert "overall.outlook 只能是“吉”，不得输出“凶”" in correction_prompt
    assert "普通排盘事实包装成不利因素" in correction_prompt


@pytest.mark.asyncio
async def test_full_pipeline_refuses_second_invalid_result(knowledge_db: Path) -> None:
    provider = SequenceProvider(
        [
            question_category(),
            conclusion(valid_source=False),
            conclusion(valid_source=False),
        ]
    )
    divination = service(knowledge_db, provider)

    with pytest.raises(DivinationValidationError) as caught:
        await divination.divine(
            DivinationRequest.model_validate(request_payload())
        )

    assert len(provider.calls) == 3
    assert "unknown_source_id" in {
        issue.code for issue in caught.value.second.issues
    }


def test_divination_api_returns_structured_result(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [question_category(), conclusion(valid_source=True)]
    )
    app.dependency_overrides[get_divination_service] = lambda: service(
        knowledge_db,
        provider,
    )

    response = TestClient(app).post(
        "/api/v1/divinations",
        json=request_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interpretation"]["overall"]["outlook"] == "吉"
    assert payload["outcome_analysis"]["guardrail"] == "仅有利主证"
    assert payload["sources"]
    assert payload["case_evidence"]
    assert len(payload["case_evidence"]) == 3
    assert payload["case_evidence"][0]["match_reasons"]
    assert payload["input_summary"]["category"] == "求财"
    assert payload["useful_god"]["selection_mode"] == "relative"
    assert payload["useful_god"]["useful_relative"] == "妻财"
    assert_fact_values_are_localized(payload["facts"])
    assert len(provider.calls) == 2
    llm_message = provider.calls[1][1].content
    assert len(llm_message) < 20_000
    facts_block = llm_message.split(
        "卦象事实（按全卦、初爻至上爻归类；事实编号仅用于引用校验）：\n",
        maxsplit=1,
    )[1].split(
        "\n\n本卦裁决证据",
        maxsplit=1,
    )[0]
    assert facts_block.count("- 爻体：") == 6
    for duplicated_type in (
        "爻之阴阳",
        "动爻",
        "静爻",
        "纳甲",
        "伏神",
        "世爻",
        "应爻",
        "六神",
    ):
        assert f"\n- {duplicated_type}：" not in facts_block
    facts_without_ids = re.sub(r"fact-\S+", "", facts_block)
    assert re.search(r"[A-Za-z]", facts_without_ids) is None


def test_question_with_multiple_topics_is_classified_by_model(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [question_category(), conclusion(valid_source=True)]
    )
    app.dependency_overrides[get_divination_service] = lambda: service(
        knowledge_db,
        provider,
    )

    response = TestClient(app).post(
        "/api/v1/divinations",
        json=request_payload(question="工作收入是否改善？"),
    )

    assert response.status_code == 200
    assert response.json()["input_summary"]["category"] == "求财"
    assert len(provider.calls) == 2


def test_user_selected_useful_god_never_requires_semantic_resolution(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [question_category(), conclusion(valid_source=True)]
    )
    app.dependency_overrides[get_divination_service] = lambda: service(
        knowledge_db,
        provider,
    )

    response = TestClient(app).post(
        "/api/v1/divinations",
        json=request_payload(),
    )

    assert response.status_code == 200
    assert response.json()["useful_god"]["useful_relative"] == "妻财"
    assert len(provider.calls) == 2
    assert provider.schemas == [QuestionCategory, DivinationConclusion]


@pytest.mark.asyncio
async def test_romance_question_uses_the_user_selected_useful_god(
    knowledge_db: Path,
) -> None:
    provider = SequenceProvider(
        [
            question_category("婚姻"),
            conclusion(valid_source=True, include_case=False),
        ]
    )
    divination = service(knowledge_db, provider)
    retrieve = divination._retrieve_knowledge

    def retrieve_without_examples(result):
        knowledge = retrieve(result)
        return type(knowledge)(sources=knowledge.sources, examples=())

    divination._retrieve_knowledge = retrieve_without_examples  # type: ignore[method-assign]
    response = await divination.divine(
        DivinationRequest.model_validate(
            request_payload(
                question="我的恋爱关系会如何发展？",
                useful_god="妻财",
            )
        )
    )

    assert response.input_summary.category == "婚姻"
    assert response.input_summary.perspective == "自占"
    assert response.useful_god is not None
    assert response.useful_god.useful_relative == "妻财"
    assert response.useful_god.status == "selected"
    assert provider.schemas == [QuestionCategory, DivinationConclusion]


def test_proxy_perspective_reaches_rule_and_response_context(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [
            question_category("求财", perspective="代占"),
            conclusion(valid_source=True),
        ]
    )
    app.dependency_overrides[get_divination_service] = lambda: service(
        knowledge_db,
        provider,
    )

    response = TestClient(app).post(
        "/api/v1/divinations",
        json=request_payload(question="替朋友问这笔生意能否获利？"),
    )

    assert response.status_code == 200
    assert response.json()["input_summary"]["perspective"] == "代占"
    assert "模型判定问占视角：代占" in provider.calls[1][1].content


def test_source_api_returns_exact_local_text(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [question_category(), conclusion(valid_source=True)]
    )
    app.dependency_overrides[get_divination_service] = lambda: service(
        knowledge_db,
        provider,
    )

    response = TestClient(app).get("/api/v1/sources/008_用神章:p0001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "008_用神章:p0001"
    assert payload["text"] in (ROOT / payload["source_path"]).read_text(encoding="utf-8")
    assert payload["is_editorial"] is False
