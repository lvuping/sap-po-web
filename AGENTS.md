# AGENTS.md — sap_po_web (SAP 구매오더 웹)

SAP S/4HANA 표준 구매오더 API(OData V4 `api_purchaseorder_2`)를 Python(httpx)으로 읽어 Streamlit 화면에 보여 주는 데모.
GitHub **공개** 저장소 `lvuping/sap-po-web`. 로컬 위치는 `sap/lecture/showcase/sap_po_web`(SAP + WEB 연동 강의의 쇼케이스).
같은 `showcase/` 의 `b1_control_room` 은 다른 프로젝트다. 건드리지 않는다.

## 왜 있나

SAP와 Python 연동을 "결과만" 보여 주는 데모 영상용(소유자 요청 2026-11-07). 표준 데이터가 있는 SAP Learning Hub 실습 시스템
T41(S/4HANA 2023, 공유 시스템, 비상업)의 원격 Windows 안에서 이 앱을 돌리고, 같은 화면의 SAP GUI ME23N과 나란히 놓는다.
그 시스템에 닿는 길 · 제약은 `sap/development/docs/2026-11-06-sap-learning-hub/README.md` §6-1.

## 명령

```bash
uv sync
uv run pytest                                              # 네트워크 없이
SAP_PO_WEB_SOURCE=sample uv run streamlit run app.py       # 지어낸 예시 데이터, http://127.0.0.1:1637
```

포트 1637: `tools/ports/README.md` 의 강의 칸(1630–1639)에 등록. 원격 PC에서도 같은 번호.

## 규칙

- **공개 저장소다.** 서버 호스트 이름 · IP · 포트, SAP 계정, 비밀번호, 실제 SAP에서 받은 데이터(캡처한 응답 포함)를 커밋하지 않는다.
  실제 응답을 개발용으로 받아 두려면 `fixtures/captured/`(git 제외)에 둔다.
- 비밀번호는 화면 입력 → 메모리만. `.env` · 로그 · 요청 목록에 넣지 않는다. 로그인 실패는 재시도하지 않는다.
- TLS 검증을 끄는 길을 만들지 않는다. OS 인증서 저장소(truststore)를 쓴다.
- **GET만.** 쓰기(구매오더 생성, 입고)는 공유 실습 시스템에 남는 변경이라 소유자 승인 없이 만들거나 실행하지 않는다.
- `fixtures/sample/` 은 지어낸 데이터다. 화면은 sample 모드에서 그 사실을 늘 표시한다. 영상 · 문서에서 예시 데이터를 실제 SAP처럼 말하지 않는다.
- 필드 이름은 T41에서 확인한 것만 믿는다(`PurchaseOrder` `PurchaseOrderType` `CompanyCode` `Supplier` `PurchaseOrderDate`, 품목
  `_PurchaseOrderItem` · `PurchaseOrderItem` `Material` `OrderQuantity` `Plant`, 2026-11-07). 그 밖의 필드는 `scripts/inspect_service.py` 로 확인한다.
- Python 3.12, 타입 힌트, 짧은 한국어 주석, 화면 문구 한국어. 새 패키지는 먼저 정한다.
- 원격 PC(러닝허브) 조작 때 키 입력은 그 브라우저 페이지에만 보낸다(System Events 키 입력 금지, 앞 창으로 샌다).
