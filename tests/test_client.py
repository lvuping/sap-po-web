from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from sap_po import (
    SERVICE_PATH,
    Connection,
    PoFilter,
    PurchaseOrderApi,
    SapApiError,
    SapAuthError,
    build_base_url,
    item_net_value,
    quote,
)
from sap_po.frames import header_pairs, headers_frame, item_rows, items_frame
from sap_po.sample import SampleService

BASE = "https://sap.example" + SERVICE_PATH


def make_api(service: SampleService | None = None, log: list | None = None) -> PurchaseOrderApi:
    service = service or SampleService()
    return PurchaseOrderApi(
        Connection(BASE, "400", "TESTER"), "pw", transport=service.transport(), on_request=(log.append if log is not None else None)
    )


# 조건식
def test_quote_escapes_single_quote() -> None:
    assert quote("O'Neil") == "'O''Neil'"


def test_filter_expression_parts() -> None:
    flt = PoFilter("nb", "1010", "90000001", date(2025, 1, 1), date(2025, 12, 31))
    assert flt.expression() == (
        "PurchaseOrderType eq 'NB' and CompanyCode eq '1010' and Supplier eq '90000001'"
        " and PurchaseOrderDate ge 2025-01-01 and PurchaseOrderDate le 2025-12-31"
    )
    assert PoFilter("").expression() == ""


@pytest.mark.parametrize(
    "flt",
    [PoFilter(company_code="10' or 1"), PoFilter(supplier="12345678901"), PoFilter(date_from=date(2026, 1, 2), date_to=date(2026, 1, 1))],
)
def test_filter_rejects_bad_input(flt: PoFilter) -> None:
    with pytest.raises(ValueError):
        flt.expression()


def test_build_base_url() -> None:
    assert build_base_url("https://h:44300/") == "https://h:44300" + SERVICE_PATH
    assert build_base_url("https://h:44300" + SERVICE_PATH) == "https://h:44300" + SERVICE_PATH
    with pytest.raises(ValueError):
        build_base_url("http://h:8000")


# 조회
def test_count_and_list_with_filter() -> None:
    api = make_api()
    assert api.count(PoFilter()) == 7  # 예시 데이터 8건 중 NB 7건
    rows = api.list_orders(PoFilter(company_code="1710"))
    assert [r["PurchaseOrder"] for r in rows] == ["4509000005", "4509000006", "4509000007"]
    assert set(rows[0]) == {"PurchaseOrder", "PurchaseOrderType", "CompanyCode", "Supplier", "PurchaseOrderDate", "DocumentCurrency"}


def test_list_follows_next_link_and_limit() -> None:
    api = make_api(SampleService(page_size=2))
    assert len(api.list_orders(PoFilter(order_type=""))) == 8
    assert len(api.list_orders(PoFilter(order_type=""), limit=3)) == 3


def test_order_detail_with_items() -> None:
    order = make_api().order("4509000006")
    assert order["Supplier"] == "90000003"
    assert [i["Material"] for i in order["_PurchaseOrderItem"]] == ["DEMO-MAT-05", "DEMO-MAT-06"]


def test_order_rejects_bad_number() -> None:
    with pytest.raises(ValueError):
        make_api().order("45'00")


def test_request_log_has_no_host_or_secret() -> None:
    log: list = []
    make_api(log=log).count(PoFilter())
    assert log[0].status == 200 and log[0].path.startswith("PurchaseOrder/$count?")
    assert "sap.example" not in log[0].path and "pw" not in log[0].path


def test_select_fallback_on_400() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "$select" in request.url.params:
            return httpx.Response(400, json={"error": {"code": "X", "message": "Property unknown"}})
        return httpx.Response(200, json={"value": [{"PurchaseOrder": "1"}]})

    api = PurchaseOrderApi(Connection(BASE, "400", "T"), "pw", transport=httpx.MockTransport(handler))
    assert api.list_orders(PoFilter()) == [{"PurchaseOrder": "1"}]


def test_401_is_auth_error_without_retry() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401)

    api = PurchaseOrderApi(Connection(BASE, "400", "T"), "bad", transport=httpx.MockTransport(handler))
    with pytest.raises(SapAuthError):
        api.count(PoFilter())
    assert len(calls) == 1
    assert calls[0].url.params["sap-client"] == "400"
    assert calls[0].headers["authorization"].startswith("Basic ")


def test_sap_error_message_v4_and_v2() -> None:
    bodies = iter(
        [
            httpx.Response(403, json={"error": {"code": "/IWFND/MED/170", "message": "No service found"}}),
            httpx.Response(500, json={"error": {"code": "E", "message": {"value": "Dump"}}}),
        ]
    )
    api = PurchaseOrderApi(Connection(BASE, "400", "T"), "pw", transport=httpx.MockTransport(lambda r: next(bodies)))
    with pytest.raises(SapApiError, match="No service found") as first:
        api.count(PoFilter())
    assert first.value.code == "/IWFND/MED/170"
    with pytest.raises(SapApiError, match="Dump"):
        api.count(PoFilter())


def test_network_error_is_sap_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    api = PurchaseOrderApi(Connection(BASE, "400", "T"), "pw", transport=httpx.MockTransport(handler))
    with pytest.raises(SapApiError, match="닿지 못했습니다"):
        api.count(PoFilter())


# 금액 · 표
def test_item_net_value() -> None:
    assert item_net_value({"NetPriceAmount": "45.00", "OrderQuantity": "100", "NetPriceQuantity": "100"}) == Decimal("45.00")
    assert item_net_value({"NetPriceAmount": 199.99, "OrderQuantity": 3}) == Decimal("599.97")
    assert item_net_value({"NetAmount": "10.5"}) == Decimal("10.5")
    assert item_net_value({"Material": "X"}) is None


def test_frames() -> None:
    api = make_api()
    assert list(headers_frame(api.list_orders(PoFilter()))["구매오더"])[:2] == ["4509000001", "4509000002"]
    order = api.order("4509000001")
    pairs = header_pairs(order)
    assert dict(zip(pairs["SAP 필드"], pairs["값"]))["Supplier"] == "90000001"
    items = items_frame(order)
    assert list(items["품목"]) == ["10", "20"] and list(items["순금액"]) == ["125.00", "320.00"]
    lines = item_rows(api.orders_with_items(PoFilter()))
    assert len(lines) == 9 and lines.groupby("통화")["순금액"].sum().round(2).to_dict() == {"EUR": 820.0, "USD": 2429.91}
