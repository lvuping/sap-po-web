"""API 응답(dict) → 화면 표(pandas). 화면 이름은 한국어, 옆에 SAP 필드 이름을 둔다."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .amounts import item_net_value
from .client import ITEM_NAV

LIST_COLUMNS = {
    "PurchaseOrder": "구매오더",
    "PurchaseOrderType": "유형",
    "CompanyCode": "회사코드",
    "Supplier": "공급업체",
    "PurchaseOrderDate": "발주일",
    "DocumentCurrency": "통화",
}

HEADER_LABELS = {
    "PurchaseOrder": "구매오더",
    "PurchaseOrderType": "문서유형",
    "CompanyCode": "회사코드",
    "PurchasingOrganization": "구매조직",
    "PurchasingGroup": "구매그룹",
    "Supplier": "공급업체",
    "PurchaseOrderDate": "발주일",
    "DocumentCurrency": "통화",
    "PaymentTerms": "지급조건",
}

ITEM_LABELS = {
    "PurchaseOrderItem": "품목",
    "Material": "자재",
    "PurchaseOrderItemText": "내역",
    "OrderQuantity": "수량",
    "PurchaseOrderQuantityUnit": "단위",
    "NetPriceAmount": "순단가",
    "NetPriceQuantity": "가격단위",
    "DocumentCurrency": "통화",
    "Plant": "플랜트",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _item_no(value: Any) -> str:
    # '00010' 과 '10' 을 같은 모양으로(ME23N 처럼 앞 0 없이)
    text = _text(value)
    return text.lstrip("0") or text


def headers_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    data = [{label: _text(row.get(field)) for field, label in LIST_COLUMNS.items()} for row in rows]
    return pd.DataFrame(data, columns=list(LIST_COLUMNS.values()))


def header_pairs(order: dict[str, Any]) -> pd.DataFrame:
    data = [
        {"항목": label, "SAP 필드": field, "값": _text(order.get(field))}
        for field, label in HEADER_LABELS.items()
        if field in order
    ]
    return pd.DataFrame(data, columns=["항목", "SAP 필드", "값"])


def items_frame(order: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in order.get(ITEM_NAV, []):
        row = {label: _text(item.get(field)) for field, label in ITEM_LABELS.items() if field in item}
        row["품목"] = _item_no(item.get("PurchaseOrderItem"))
        net = item_net_value(item)
        row["순금액"] = "" if net is None else f"{net:,.2f}"
        rows.append(row)
    return pd.DataFrame(rows)


def item_rows(orders: list[dict[str, Any]]) -> pd.DataFrame:
    """대시보드용: 품목 한 줄씩. 금액은 차트를 위해 float 로 바꾼다(표시는 통화별 합계)."""
    rows = []
    for order in orders:
        month = _text(order.get("PurchaseOrderDate"))[:7]
        for item in order.get(ITEM_NAV, []):
            net = item_net_value(item)
            rows.append(
                {
                    "구매오더": _text(order.get("PurchaseOrder")),
                    "회사코드": _text(order.get("CompanyCode")),
                    "공급업체": _text(order.get("Supplier")),
                    "월": month,
                    "통화": _text(item.get("DocumentCurrency") or order.get("DocumentCurrency")),
                    "순금액": float(net) if net is not None else 0.0,
                }
            )
    return pd.DataFrame(rows, columns=["구매오더", "회사코드", "공급업체", "월", "통화", "순금액"])
