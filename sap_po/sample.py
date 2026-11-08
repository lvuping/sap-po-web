"""SAP 없이 화면을 개발·시험할 때 쓰는 가짜 OData 서버(httpx 전송 계층).

fixtures/sample/purchase_orders.json 은 지어낸 예시 데이터다. 화면은 이 모드일 때 그 사실을 늘 표시한다.
지원하는 것: $filter(eq · ge · le 를 and 로 이은 것), $select, $expand, $top, $count, 한 건 조회, 서버 쪽 나눠 주기.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode

import httpx

from .client import ITEM_NAV

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample" / "purchase_orders.json"
_TERM = re.compile(r"^(\w+) (eq|ge|le) (?:'((?:[^']|'')*)'|([0-9-]+))$")


def load_orders(path: Path = FIXTURE) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["value"]


def _match(order: dict[str, Any], expr: str) -> bool:
    for term in filter(None, expr.split(" and ")):
        m = _TERM.match(term.strip())
        if not m:
            raise ValueError(f"예시 서버가 모르는 조건: {term}")
        field, op, text, number = m.groups()
        want = text.replace("''", "'") if text is not None else number
        have = str(order.get(field, ""))
        if (op == "eq" and have != want) or (op == "ge" and have < want) or (op == "le" and have > want):
            return False
    return True


class SampleService:
    def __init__(self, orders: list[dict[str, Any]] | None = None, page_size: int = 50) -> None:
        self.orders = sorted(orders if orders is not None else load_orders(), key=lambda o: o["PurchaseOrder"])
        self.page_size = page_size

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _shape(self, order: dict[str, Any], select: str, expand: bool) -> dict[str, Any]:
        head = {k: v for k, v in order.items() if k != ITEM_NAV}
        if select:
            head = {k: head.get(k) for k in select.split(",")}
        if expand:
            head[ITEM_NAV] = order.get(ITEM_NAV, [])
        return head

    def handle(self, request: httpx.Request) -> httpx.Response:
        q = {k: v[-1] for k, v in parse_qs(request.url.query.decode(), keep_blank_values=True).items()}
        tail = request.url.path.rsplit("/purchaseorder/0001/", 1)[-1]
        expand = q.get("$expand") == ITEM_NAV

        if m := re.fullmatch(r"PurchaseOrder\('(\d+)'\)", tail):
            for order in self.orders:
                if order["PurchaseOrder"] == m.group(1):
                    return httpx.Response(200, json=self._shape(order, "", expand))
            return httpx.Response(404, json={"error": {"code": "404", "message": "Not found"}})

        rows = [o for o in self.orders if _match(o, q.get("$filter", ""))]
        if tail == "PurchaseOrder/$count":
            return httpx.Response(200, text=str(len(rows)))
        if tail != "PurchaseOrder":
            return httpx.Response(404, json={"error": {"code": "404", "message": "No such resource"}})

        rows = rows[: int(q.get("$top", len(rows)))]
        skip = int(q.get("$skiptoken", "0"))
        page = rows[skip : skip + self.page_size]
        body: dict[str, Any] = {"value": [self._shape(o, q.get("$select", ""), expand) for o in page]}
        if skip + self.page_size < len(rows):
            nxt = {k: v for k, v in q.items() if k != "sap-client"} | {"$skiptoken": str(skip + self.page_size)}
            body["@odata.nextLink"] = "PurchaseOrder?" + urlencode(nxt)
        return httpx.Response(200, json=body)
