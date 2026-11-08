"""SAP S/4HANA 표준 구매오더 API(OData V4, api_purchaseorder_2) 읽기 클라이언트.

GET 만 한다. 비밀번호는 httpx 클라이언트의 메모리 안에만 있고 파일·로그·화면에 남기지 않는다.
"""

from __future__ import annotations

import ssl
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import unquote, unquote_plus

import httpx

from .odata import PoFilter, quote

# 서비스 경로는 표준이다. 호스트·포트는 시스템마다 달라서 저장소에 적지 않는다.
SERVICE_PATH = "/sap/opu/odata4/sap/api_purchaseorder_2/srvd_a2x/sap/purchaseorder/0001"
ITEM_NAV = "_PurchaseOrderItem"
LIST_SELECT = (
    "PurchaseOrder",
    "PurchaseOrderType",
    "CompanyCode",
    "Supplier",
    "PurchaseOrderDate",
    "DocumentCurrency",
)


class SapApiError(Exception):
    """SAP 가 오류로 답했거나 닿지 못했을 때. 글은 화면에 그대로 보여도 된다."""

    def __init__(self, message: str, status: int | None = None, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class SapAuthError(SapApiError):
    """로그인 실패. 계정 잠김을 막으려고 다시 시도하지 않는다."""


@dataclass(frozen=True)
class Connection:
    base_url: str  # 예: https://<호스트>:<포트> + SERVICE_PATH
    client: str = "400"
    user: str = ""
    label: str = ""  # 화면에 보일 시스템 이름(예: "T41"). 비우면 호스트를 감춘다
    timeout: float = 20.0

    def describe(self) -> str:
        system = self.label or "SAP"
        return f"{system} · client {self.client} · {self.user or '사용자 없음'}"


@dataclass(frozen=True)
class RequestLog:
    at: str
    method: str
    path: str  # 서비스 경로 뒤쪽(쿼리 포함). 호스트·인증 정보는 넣지 않는다
    status: int
    millis: int


def os_trust_context() -> ssl.SSLContext:
    """운영체제 인증서 저장소로 서버 인증서를 검증한다(회사 내부 CA 포함)."""
    import truststore

    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def build_base_url(host_url: str) -> str:
    """'https://host:port' 또는 서비스 전체 주소를 받아 서비스 루트로 맞춘다."""
    url = host_url.strip().rstrip("/")
    if not url.startswith("https://"):
        raise ValueError("주소는 https:// 로 시작해야 합니다.")
    return url if url.endswith(SERVICE_PATH) else url + SERVICE_PATH


def _sap_message(res: httpx.Response) -> tuple[str, str]:
    try:
        err = res.json().get("error", {})
    except ValueError:
        return "", res.text[:200]
    msg = err.get("message", "")
    if isinstance(msg, dict):  # OData V2 모양
        msg = msg.get("value", "")
    return str(err.get("code", "")), str(msg)


class PurchaseOrderApi:
    def __init__(
        self,
        conn: Connection,
        password: str | None,
        *,
        transport: httpx.BaseTransport | None = None,
        on_request: Callable[[RequestLog], None] | None = None,
    ) -> None:
        self.conn = conn
        self._on_request = on_request
        self._root = httpx.URL(conn.base_url.rstrip("/") + "/")
        self._http = httpx.Client(
            base_url=self._root,
            auth=(conn.user, password) if password else None,
            headers={"Accept": "application/json"},
            timeout=conn.timeout,
            follow_redirects=False,
            trust_env=False,
            verify=os_trust_context() if transport is None else True,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    # 요청 한 번
    def _get(self, url: str, params: dict[str, str] | None = None, *, accept: str | None = None) -> httpx.Response:
        # httpx 는 클라이언트 기본 params 가 있으면 주소의 쿼리를 버린다 → 요청마다 직접 합친다
        target = httpx.URL(url)
        query = {"sap-client": self.conn.client, **dict(target.params.multi_items()), **(params or {})}
        headers = {"Accept": accept} if accept else None
        started = time.perf_counter()
        status = 0
        try:
            res = self._http.get(target.copy_with(query=None), params=query, headers=headers)
            status = res.status_code
        except httpx.TimeoutException as exc:
            raise SapApiError("SAP 응답이 시간 안에 오지 않았습니다.") from exc
        except httpx.HTTPError as exc:
            raise SapApiError(f"SAP 서버에 닿지 못했습니다 ({type(exc).__name__}).") from exc
        finally:
            self._log(url if status == 0 else str(res.url), status, started)

        if status == 401:
            raise SapAuthError(
                "로그인 실패: 사용자와 비밀번호를 확인하세요. 계정 잠김을 막으려고 다시 시도하지 않습니다.", 401
            )
        if res.is_redirect:
            raise SapAuthError(f"SAP 가 로그인 화면으로 돌려보냈습니다 (HTTP {status}).", status)
        if status >= 400:
            code, msg = _sap_message(res)
            raise SapApiError(f"SAP 오류 HTTP {status}: {msg or '내용 없음'}", status, code)
        return res

    def _log(self, url: str, status: int, started: float) -> None:
        if self._on_request is None:
            return
        raw, _, query = str(url).partition("?")
        full = unquote(raw) + ("?" + unquote_plus(query) if query else "")
        root = unquote(str(self._root))
        if full.startswith(root):
            path = full[len(root) :]
        elif "://" in full:  # 서비스 밖 주소: 호스트는 빼고 경로만
            path = "/" + full.split("://", 1)[1].split("/", 1)[-1]
        else:  # 연결 전에 실패한 상대 경로
            path = full
        self._on_request(
            RequestLog(
                at=datetime.now().strftime("%H:%M:%S"),
                method="GET",
                path=path,
                status=status,
                millis=round((time.perf_counter() - started) * 1000),
            )
        )

    def _rows(self, path: str, params: dict[str, str], limit: int) -> Iterator[dict[str, Any]]:
        """value 배열을 읽고, 서버가 나눠 주면 @odata.nextLink 를 따라간다."""
        res = self._get(path, params)
        got = 0
        while True:
            body = res.json()
            for row in body.get("value", []):
                yield row
                got += 1
                if got >= limit:
                    return
            next_link = body.get("@odata.nextLink")
            if not next_link:
                return
            res = self._get(str(self._root.join(next_link)))

    # 조회
    def metadata(self) -> str:
        """서비스 정의(CSDL XML). JSON 만 받겠다고 하면 SAP 가 406 을 준다."""
        return self._get("$metadata", accept="application/xml").text

    def count(self, flt: PoFilter) -> int:
        params = {"$filter": expr} if (expr := flt.expression()) else {}
        return int(self._get("PurchaseOrder/$count", params).text.strip())

    def list_orders(self, flt: PoFilter, *, limit: int = 200) -> list[dict[str, Any]]:
        params = {"$select": ",".join(LIST_SELECT), "$orderby": "PurchaseOrder", "$top": str(limit)}
        if expr := flt.expression():
            params["$filter"] = expr
        try:
            return list(self._rows("PurchaseOrder", params, limit))
        except SapApiError as exc:
            if exc.status != 400:
                raise
            # 시스템에 따라 없는 필드가 있으면 $select 없이 다시 묻는다
            params.pop("$select")
            return list(self._rows("PurchaseOrder", params, limit))

    def orders_with_items(self, flt: PoFilter, *, limit: int = 500) -> list[dict[str, Any]]:
        params = {"$expand": ITEM_NAV, "$orderby": "PurchaseOrder", "$top": str(limit)}
        if expr := flt.expression():
            params["$filter"] = expr
        return list(self._rows("PurchaseOrder", params, limit))

    def order(self, number: str) -> dict[str, Any]:
        number = number.strip()
        if not number.isdigit() or len(number) > 10:
            raise ValueError("구매오더 번호는 숫자 10자리 이내입니다.")
        return self._get(f"PurchaseOrder({quote(number)})", {"$expand": ITEM_NAV}).json()
