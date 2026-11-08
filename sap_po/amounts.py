"""금액 계산. 부동소수 대신 Decimal 로 한다."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def item_net_value(item: dict[str, Any]) -> Decimal | None:
    """품목 순금액 = 순단가 × 수량 ÷ 가격단위. API 가 NetAmount 를 주면 그 값을 쓴다."""
    if (net := to_decimal(item.get("NetAmount"))) is not None:
        return net
    price = to_decimal(item.get("NetPriceAmount"))
    qty = to_decimal(item.get("OrderQuantity"))
    per = to_decimal(item.get("NetPriceQuantity")) or Decimal(1)
    if price is None or qty is None:
        return None
    return (price * qty / per).quantize(Decimal("0.01"))
