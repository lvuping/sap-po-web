"""OData V4 조회 조건($filter)을 안전하게 만든다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_CODE = re.compile(r"^[A-Za-z0-9]+$")


def quote(value: str) -> str:
    """OData 문자열 리터럴. 작은따옴표는 두 번 써서 이스케이프한다."""
    return "'" + value.replace("'", "''") + "'"


def _code(value: str, label: str, max_len: int) -> str:
    value = value.strip().upper()
    if value and (len(value) > max_len or not _CODE.match(value)):
        raise ValueError(f"{label}는 영문·숫자 {max_len}자 이내입니다: {value!r}")
    return value


@dataclass(frozen=True)
class PoFilter:
    """구매오더 목록 조건. 빈 값은 조건에서 뺀다."""

    order_type: str = "NB"
    company_code: str = ""
    supplier: str = ""
    date_from: date | None = None
    date_to: date | None = None

    def expression(self) -> str:
        parts: list[str] = []
        if order_type := _code(self.order_type, "문서유형", 4):
            parts.append(f"PurchaseOrderType eq {quote(order_type)}")
        if company := _code(self.company_code, "회사코드", 4):
            parts.append(f"CompanyCode eq {quote(company)}")
        if supplier := _code(self.supplier, "공급업체", 10):
            parts.append(f"Supplier eq {quote(supplier)}")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("시작일이 종료일보다 늦습니다.")
        if self.date_from:
            parts.append(f"PurchaseOrderDate ge {self.date_from.isoformat()}")
        if self.date_to:
            parts.append(f"PurchaseOrderDate le {self.date_to.isoformat()}")
        return " and ".join(parts)
