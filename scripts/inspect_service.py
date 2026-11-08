"""SAP 쪽 구매오더 서비스가 어떤 필드를 주는지 본다(GET 만).

실행(원격 PC): uv run python scripts/inspect_service.py --host https://<호스트>:<포트> --user <사용자>
- $metadata 에서 PurchaseOrder · PurchaseOrderItem 의 필드와 내비게이션 이름을 출력한다.
- 구매오더 한 건(--po)을 품목까지 읽어 어떤 필드에 값이 있는지 출력한다.
- 비밀번호는 실행할 때 숨겨서 받는다. 파일에 저장하지 않는다. 로그인 실패는 다시 시도하지 않는다.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sap_po import Connection, PoFilter, PurchaseOrderApi, SapApiError, build_base_url  # noqa: E402

WANTED = ("PurchaseOrder", "PurchaseOrderItem")


def entity_fields(metadata_xml: str, set_names: tuple[str, ...]) -> list[tuple[str, list[str], list[str]]]:
    """엔터티 세트 이름 → (세트, 필드, 내비게이션). RAP V4 는 타입 이름이 세트와 다르다(PurchaseOrder → PurchaseOrderType)."""
    root = ET.fromstring(metadata_xml)
    types = {n.attrib.get("Name"): n for n in root.iter() if n.tag.endswith("}EntityType")}
    sets = {n.attrib.get("Name"): n.attrib.get("EntityType", "") for n in root.iter() if n.tag.endswith("}EntitySet")}
    out = []
    for name in set_names:
        node = types.get(sets.get(name, name).rsplit(".", 1)[-1])
        if node is None:  # 세트 정의가 없는 서비스: 타입 이름이 세트와 같다고 본다
            node = types.get(name)
        if node is None:
            continue
        props = [p.attrib["Name"] for p in node if p.tag.endswith("}Property")]
        navs = [p.attrib["Name"] for p in node if p.tag.endswith("}NavigationProperty")]
        out.append((name, props, navs))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--client", default="400")
    ap.add_argument("--user", required=True)
    ap.add_argument("--po", default="")
    args = ap.parse_args()

    secret = getpass.getpass("SAP 비밀번호(화면에 보이지 않음): ")
    api = PurchaseOrderApi(Connection(build_base_url(args.host), args.client, args.user.upper()), secret)
    del secret
    try:
        for name, props, navs in entity_fields(api.metadata(), WANTED):
            print(f"[{name}] 필드 {len(props)}개")
            print("  " + ", ".join(props))
            print(f"  내비게이션: {', '.join(navs) or '없음'}")
        print(f"NB 구매오더 수: {api.count(PoFilter())}")
        if args.po:
            order = api.order(args.po)
            filled = sorted(k for k, v in order.items() if v not in (None, "", []) and not k.startswith("@"))
            print(f"[{args.po}] 값이 있는 헤더 필드: {', '.join(filled)}")
            for item in order.get("_PurchaseOrderItem", [])[:1]:
                filled = sorted(k for k, v in item.items() if v not in (None, "") and not k.startswith("@"))
                print(f"  첫 품목의 값이 있는 필드: {', '.join(filled)}")
    except SapApiError as exc:
        print(f"실패: {exc}")
        return 1
    finally:
        api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
