from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_divination_service
from app.api.schemas import DivinationRequest, DivinationResponse, SourceOutput
from app.divination.service import (
    DivinationService,
    DivinationValidationError,
    KnowledgeBaseUnavailable,
    UsefulGodResolutionRequired,
)
from app.llm.errors import LLMConfigurationError, LLMError


router = APIRouter(prefix="/api/v1", tags=["divination"])


@router.post("/divinations", response_model=DivinationResponse)
async def divination(
    request: DivinationRequest,
    service: Annotated[DivinationService, Depends(get_divination_service)],
) -> DivinationResponse:
    try:
        return await service.divine(request)
    except KnowledgeBaseUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "knowledge_base_unavailable", "message": str(error)},
        ) from error
    except UsefulGodResolutionRequired as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "useful_god_resolution_required",
                "message": str(error),
                "rationale": list(error.rationale),
            },
        ) from error
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "llm_configuration_error", "message": str(error)},
        ) from error
    except LLMError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "llm_request_error", "message": str(error)},
        ) from error
    except DivinationValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "llm_validation_failed",
                "message": str(error),
                "issues": [
                    issue.model_dump(mode="json") for issue in error.second.issues
                ],
            },
        ) from error


@router.get("/sources/{source_id:path}", response_model=SourceOutput)
async def source(
    source_id: str,
    service: Annotated[DivinationService, Depends(get_divination_service)],
) -> SourceOutput:
    try:
        result = service.get_source(source_id)
    except KnowledgeBaseUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "knowledge_base_unavailable", "message": str(error)},
        ) from error
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "source_not_found", "message": f"原文引用不存在：{source_id}"},
        )
    return result
