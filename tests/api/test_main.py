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
    assert response.headers["cache-control"] == "no-store"
    assert "初爻在下、上爻在上" in response.text
    assert '<select id="useful-god" name="useful_god" required>' in response.text
    assert "具体主用爻由系统依据《增删卜易》确定" in response.text
    assert "占问类型" not in response.text
    assert "自占" not in response.text
    assert "代占" not in response.text
    script_response = client.get("/static/app.js")
    assert script_response.headers["cache-control"] == "no-store"
    script = script_response.text
    assert '["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]' in script
    assert "/api/v1/categories" not in script
    assert "function ensureUsefulGodSelector()" in script
    assert "useful_god: ensureUsefulGodSelector().value" in script
    assert "useful_god_line" not in script
    assert "卦例参考（不参与吉凶权重）" in script
    assert "fact.related_lines?.length" in script
    assert "lineNames[position - 1]" in script
    assert "function sourceLabel(sourceId)" in script
    assert "第${match[3]}段" in script
    assert '["事实编号", (fact) => fact.id]' in script


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
