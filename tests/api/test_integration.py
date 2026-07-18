from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_divination_service
from app.api.schemas import DivinationRequest
from app.config import Settings
from app.divination.service import DivinationService, DivinationValidationError
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
    QuestionApplication,
    RisksAndUncertainties,
    SourceCitation,
    SpecialPatternsAnalysis,
    TimingSelection,
    UsefulGodDecision,
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
) -> dict:
    return {
        "question": question,
        "calendar": {
            "year": 2026,
            "month": 7,
            "day": 17,
            "hour": 9,
            "timezone": "Asia/Shanghai",
        },
        "lines": [7, 8, 6, 9, 7, 8],
    }


def useful_god_decision(*, valid_source: bool = True) -> UsefulGodDecision:
    citation = (
        SourceCitation(
            source_id="008_用神章:p0006",
            quote="占货财、珠宝、金银、仓库、钱粮",
        )
        if valid_source
        else SourceCitation(source_id="999_伪造章:p0001", quote="伪造原文")
    )
    return UsefulGodDecision(
        category="求财",
        target="本次求财",
        mode="relative",
        useful_relative="妻财",
        rationale="用户询问求财，依原文以妻财爻为用神。",
        citations=[citation],
    )


def conclusion(*, valid_source: bool = True) -> DivinationConclusion:
    citation = (
        SourceCitation(
            source_id="008_用神章:p0006",
            quote="凡我驱使之人，皆以财爻为用神。",
        )
        if valid_source
        else SourceCitation(source_id="999_伪造章:p0001", quote="伪造原文")
    )
    judgement = Judgement(
        statement="排盘事实与原文均已列出，现有证据不足以作确定吉凶。",
        fact_ids=["fact-primary-hexagram"],
        citations=[citation],
    )
    return DivinationConclusion(
        overall=OverallConclusion(
            outlook="凶",
            summary="本次求财偏难",
            judgements=[judgement],
        ),
        question_application=QuestionApplication(
            focus="本次所问求财能否办成",
            favorable=[],
            adverse=[
                Judgement(
                    statement="本卦不利因素应落实为本次求财推进困难。",
                    fact_ids=["fact-primary-hexagram"],
                )
            ],
            synthesis=Judgement(
                statement="综合本卦事实，本次求财偏难，不只是抽象术语判断。",
                fact_ids=["fact-primary-hexagram"],
            ),
        ),
        case_analysis=CaseAnalysis(
            comparisons=[
                CaseComparison(
                    example_id=CASE_ID,
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
    response = TestClient(app).post("/api/v1/chart", json=request_payload())

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


@pytest.mark.asyncio
async def test_full_pipeline_retries_invalid_citation_once(knowledge_db: Path) -> None:
    provider = SequenceProvider(
        [
            useful_god_decision(),
            conclusion(valid_source=False),
            conclusion(valid_source=True),
        ]
    )
    divination = service(knowledge_db, provider)

    response = await divination.divine(
        DivinationRequest.model_validate(request_payload())
    )

    assert response.interpretation.overall.outlook == "凶"
    assert len(provider.calls) == 3
    assert provider.schemas == [
        UsefulGodDecision,
        DivinationConclusion,
        DivinationConclusion,
    ]
    assert "上一次的结构化结果未通过校验" in provider.calls[2][-1].content
    assert response.sources
    assert response.case_evidence
    assert len(response.case_evidence) == 1
    assert response.case_evidence[0].judgement.content_type.value == "example_judgement"
    assert all(not source.is_editorial for source in response.sources)
    assert any(source.source_id == "008_用神章:p0006" for source in response.sources)


@pytest.mark.asyncio
async def test_full_pipeline_refuses_second_invalid_result(knowledge_db: Path) -> None:
    provider = SequenceProvider(
        [
            useful_god_decision(),
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
        [useful_god_decision(), conclusion(valid_source=True)]
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
    assert payload["interpretation"]["overall"]["outlook"] == "凶"
    assert payload["sources"]
    assert payload["case_evidence"]
    assert len(payload["case_evidence"]) == 1
    assert payload["case_evidence"][0]["match_reasons"]
    assert payload["input_summary"]["category"] == "求财"
    assert payload["useful_god"]["selection_mode"] == "relative"
    assert payload["useful_god"]["useful_relative"] == "妻财"
    assert len(provider.calls) == 2
    assert len(provider.calls[1][1].content) < 20_000


def test_question_with_multiple_topics_is_classified_by_model(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [useful_god_decision(), conclusion(valid_source=True)]
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


def test_invalid_useful_god_citation_is_corrected_before_interpretation(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [
            useful_god_decision(valid_source=False),
            useful_god_decision(valid_source=True),
            conclusion(valid_source=True),
        ]
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
    assert len(provider.calls) == 3
    assert provider.schemas == [
        UsefulGodDecision,
        UsefulGodDecision,
        DivinationConclusion,
    ]
    assert "用神判定引用了未提供的原文出处" in provider.calls[1][-1].content


def test_source_api_returns_exact_local_text(
    knowledge_db: Path,
    override_cleanup: None,
) -> None:
    provider = SequenceProvider(
        [useful_god_decision(), conclusion(valid_source=True)]
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
