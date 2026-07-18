"""Exceptions raised by the LLM provider layer.

These are the only exception types ``app.divination.service`` (or any other
caller) should need to catch when talking to an :class:`app.llm.base.LLMProvider`.
Provider implementations must translate every SDK-specific error into one of
these types instead of letting SDK exceptions leak to callers.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for every error raised by the ``app.llm`` package."""


class LLMConfigurationError(LLMError):
    """The selected provider is missing required configuration.

    Raised eagerly (at provider construction time), never silently swapped
    for another provider. Per implementation_plan.md §11.1, a missing
    configuration for the *currently selected* provider must fail loudly.
    """


class LLMDependencyError(LLMError):
    """The official SDK package required by the selected provider is missing.

    Provider modules import their SDK lazily (only when the provider is
    actually constructed) so that selecting, say, ``anthropic`` never
    requires the ``openai`` package to be installed, and vice versa.
    """


class LLMRequestError(LLMError):
    """The upstream API call failed for a reason other than timeout/rate limit."""


class LLMTimeoutError(LLMRequestError):
    """The upstream API call timed out."""


class LLMRateLimitError(LLMRequestError):
    """The upstream API rejected the call due to rate limiting."""


class LLMResponseError(LLMError):
    """The upstream response could not be parsed into the requested schema.

    Covers non-JSON content, JSON that does not validate against the
    requested Pydantic schema, and structurally unexpected SDK responses
    (e.g. no choices, no tool_use block).
    """
