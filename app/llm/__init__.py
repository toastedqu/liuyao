"""Provider-agnostic LLM layer: messages, structured schemas, prompts and
provider adapters for OpenAI, Azure OpenAI and Anthropic.

Typical usage from ``app.divination.service`` (not part of this package)::

    from app.llm import get_llm_provider, build_messages, DivinationConclusion

    provider = get_llm_provider()  # reads LLM_PROVIDER + provider env vars
    messages = build_messages(context, DivinationConclusion)
    result = await provider.generate_structured(messages, DivinationConclusion)
"""

from __future__ import annotations

from app.llm.base import LLMProvider, Message, parse_structured_json, validate_structured_payload
from app.llm.context import (
    DivinationRequestContext,
    ExampleContext,
    FactContext,
    SourceContext,
    TimingCandidateContext,
)
from app.llm.errors import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.llm.factory import get_llm_provider
from app.llm.prompts import (
    FORBIDDEN_TERMS,
    build_correction_messages,
    build_messages,
    build_system_prompt,
    build_user_message,
)
from app.llm.schemas import (
    CaseAnalysis,
    CaseComparison,
    DivinationConclusion,
    Judgement,
    LineAssertion,
    LineProperty,
    MonthDayAnalysis,
    MovingLinesAnalysis,
    OverallConclusion,
    QuestionApplication,
    RiskItem,
    RisksAndUncertainties,
    SourceCitation,
    SpecialPattern,
    SpecialPatternsAnalysis,
    TimingSelection,
    UsefulGodAnalysis,
)

__all__ = [
    "LLMProvider",
    "Message",
    "parse_structured_json",
    "validate_structured_payload",
    "DivinationRequestContext",
    "ExampleContext",
    "FactContext",
    "SourceContext",
    "TimingCandidateContext",
    "LLMConfigurationError",
    "LLMDependencyError",
    "LLMError",
    "LLMRateLimitError",
    "LLMRequestError",
    "LLMResponseError",
    "LLMTimeoutError",
    "get_llm_provider",
    "FORBIDDEN_TERMS",
    "build_correction_messages",
    "build_messages",
    "build_system_prompt",
    "build_user_message",
    "DivinationConclusion",
    "CaseAnalysis",
    "CaseComparison",
    "Judgement",
    "LineAssertion",
    "LineProperty",
    "MonthDayAnalysis",
    "MovingLinesAnalysis",
    "OverallConclusion",
    "QuestionApplication",
    "RiskItem",
    "RisksAndUncertainties",
    "SourceCitation",
    "SpecialPattern",
    "SpecialPatternsAnalysis",
    "TimingSelection",
    "UsefulGodAnalysis",
]
