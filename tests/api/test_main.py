from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_removed_categories_endpoint() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/v1/categories").status_code == 404


def test_frontend_marks_line_order_and_has_six_groups() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "初爻在下、上爻在上" in response.text
    assert "占问类型" not in response.text
    assert "自占" not in response.text
    assert "代占" not in response.text
    script = client.get("/static/app.js").text
    assert '["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]' in script
    assert "/api/v1/categories" not in script
    assert "卦例类比" in script


def test_unsupported_calendar_year_returns_structured_422() -> None:
    response = client.post(
        "/api/v1/chart",
        json={
            "question": "测试历法边界",
            "calendar": {
                "year": 1,
                "month": 7,
                "day": 1,
                "hour": 12,
                "timezone": "Asia/Shanghai",
            },
            "lines": [7, 8, 7, 8, 7, 8],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "calendar_error"
