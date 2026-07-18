from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_chart import router as chart_router
from app.api.routes_divination import router as divination_router
from app.calendar.errors import CalendarError


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(
    title="《增删卜易》六爻占卜系统",
    version="0.1.0",
    description="确定性排盘、原文检索和受约束的带引用断卦。",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(chart_router)
app.include_router(divination_router)


@app.exception_handler(CalendarError)
async def calendar_error_handler(
    _request: Request,
    error: CalendarError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "calendar_error",
                "message": str(error),
            }
        },
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
