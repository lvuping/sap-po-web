"""화면 시험: 예시 데이터 모드로 앱을 실제로 돌려 본다(포트를 열지 않는다)."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("SAP_PO_WEB_SOURCE", "sample")
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_sample_mode_connects_and_says_so(app: AppTest) -> None:
    assert any("예시 데이터 모드" in w.value for w in app.sidebar.warning)
    assert any("연결됨" in s.value for s in app.sidebar.success)
    assert [t.label for t in app.tabs] == ["구매오더 목록", "구매오더 상세", "대시보드", "연결 구조"]


def test_search_detail_and_dashboard(app: AppTest) -> None:
    # 목록: 기본 조건(NB)으로 조회
    search = next(b for b in app.get("form_submit_button") if b.label == "조회")
    search.click().run()
    assert not app.exception
    assert app.metric[0].value == "7건"

    # 상세: 번호를 넣고 불러오기
    number = next(t for t in app.text_input if t.label == "구매오더 번호")
    number.input("4509000001")
    next(b for b in app.get("form_submit_button") if b.label == "불러오기").click().run()
    assert not app.exception
    assert any(s.value == "구매오더 4509000001" for s in app.subheader)

    # 대시보드
    next(b for b in app.button if b.label == "SAP 에서 불러와 집계").click().run()
    assert not app.exception
    values = {m.label: m.value for m in app.metric}
    assert values["구매오더"] == "7" and values["품목"] == "9" and values["공급업체"] == "4"


def test_bad_supplier_shows_error(app: AppTest) -> None:
    next(t for t in app.text_input if t.label == "공급업체").input("ABC'DEF")
    next(b for b in app.get("form_submit_button") if b.label == "조회").click().run()
    assert any("공급업체" in e.value for e in app.error)
