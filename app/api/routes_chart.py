from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_divination_service
from app.api.schemas import ChartRequest, ChartResponse
from app.divination.service import DivinationService


router = APIRouter(prefix="/api/v1", tags=["chart"])


@router.post("/chart", response_model=ChartResponse)
async def chart(
    request: ChartRequest,
    service: Annotated[DivinationService, Depends(get_divination_service)],
) -> ChartResponse:
    return service.chart_response(request)
