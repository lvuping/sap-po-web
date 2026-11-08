# SAP 구매오더 웹

SAP S/4HANA의 **표준 구매오더 API**(OData V4 `api_purchaseorder_2`)를 Python으로 불러 웹 화면에 보여 주는 작은 데모입니다.
ABAP 개발이나 SAP 쪽 설정 없이, 이미 켜져 있는 표준 API만 씁니다. **읽기 전용**(HTTP GET)입니다.

| 화면 | 하는 일 |
|---|---|
| 구매오더 목록 | 문서유형 · 회사코드 · 공급업체 · 발주일로 거르고, 조건에 맞는 건수를 SAP에 직접 셉니다(`$count`) |
| 구매오더 상세 | 번호 하나를 품목까지 읽습니다(`$expand=_PurchaseOrderItem`). 화면 이름 옆에 SAP 필드 이름을 둡니다 |
| 대시보드 | 회사코드별 · 공급업체별 · 월별 집계. 순금액 = 순단가 × 수량 ÷ 가격단위, 통화별 합계 |
| 연결 구조 | 브라우저 → Python 앱 → SAP Gateway → S/4HANA 그림과, 방금 SAP에 보낸 요청 목록(경로 · 상태 · 걸린 시간) |

## 빨리 해 보기 (SAP 없이)

```bash
uv sync
SAP_PO_WEB_SOURCE=sample uv run streamlit run app.py
```

브라우저에서 <http://127.0.0.1:1637> 을 엽니다. 이 모드의 데이터(`fixtures/sample/`)는 **지어낸 예시**이고, 화면 왼쪽에 늘 그렇게 표시됩니다.

## 실제 SAP에 붙이기

필요한 것

- Python 3.12와 [uv](https://docs.astral.sh/uv/)
- S/4HANA(온프레미스 · 프라이빗 클라우드)에 `api_purchaseorder_2`(OData V4)가 게시돼 있을 것(`/IWFND/V4_ADMIN`)
- 구매오더를 읽을 권한이 있는 SAP 사용자, 그리고 그 서버에 HTTPS로 닿는 PC

macOS · Linux

```bash
export SAP_PO_WEB_HOST="https://<호스트>:<HTTPS 포트>"   # 서비스 경로는 앱이 붙입니다
export SAP_PO_WEB_LABEL="QAS"                           # 화면에 보일 시스템 이름(선택)
export SAP_PO_WEB_USER="<사용자>"                        # 기본값(선택)
uv run streamlit run app.py
```

Windows PowerShell

```powershell
$env:SAP_PO_WEB_HOST = "https://<호스트>:<HTTPS 포트>"
$env:SAP_PO_WEB_LABEL = "QAS"
$env:SAP_PO_WEB_USER = "<사용자>"
uv run streamlit run app.py
```

왼쪽에서 클라이언트와 비밀번호를 넣고 **연결**을 누릅니다. 연결되면 표준 구매오더(NB) 건수가 보입니다.

관리자 권한이 없는 Windows(교육용 원격 PC 등)에서도 됩니다. uv는 사용자 폴더에 설치되고([설치 안내](https://docs.astral.sh/uv/getting-started/installation/)), git은 설치기 없는 [MinGit](https://github.com/git-for-windows/git/releases) zip을 풀어 쓰면 됩니다.

### 내 시스템에 어떤 필드가 있는지 보기

```bash
uv run python scripts/inspect_service.py --host "https://<호스트>:<포트>" --user <사용자> --po <구매오더 번호>
```

`$metadata`의 구매오더 · 품목 필드와, 구매오더 한 건에서 값이 채워진 필드를 출력합니다. GET만 합니다.

## 보안

- 비밀번호는 화면에서만 받고, 연결된 동안 이 앱의 메모리에만 있습니다. 파일 · 환경변수 · 로그 · 화면 요청 목록에 남기지 않습니다.
- 로그인이 실패하면 다시 시도하지 않습니다(계정 잠김 방지).
- 서버 인증서는 **운영체제 인증서 저장소**로 검증합니다([truststore](https://github.com/sethmlarson/truststore)). 회사 내부 CA가 발급한 인증서도 그 PC의 OS가 믿으면 통과합니다. 검증을 끄는 옵션은 없습니다.
- 저장소에는 서버 주소 · 계정 · 실제 SAP 데이터를 넣지 않습니다.

## 하지 않는 것

- 쓰기(구매오더 생성 · 변경, 입고). 이 데모는 조회만 합니다.
- 공급업체 이름. 구매오더 API는 공급업체 번호만 줍니다. 이름은 비즈니스 파트너 API를 따로 불러야 합니다.

## 개발

```bash
uv run pytest        # 가짜 OData 서버(httpx MockTransport)로 돌아서 네트워크를 쓰지 않습니다
```

| 경로 | 내용 |
|---|---|
| `app.py` | Streamlit 화면 |
| `sap_po/client.py` | OData V4 읽기 클라이언트(오류 · 로그인 실패 · 다음 페이지 따라가기 · 요청 기록) |
| `sap_po/odata.py` | `$filter` 만들기(입력 검사 · 따옴표 이스케이프) |
| `sap_po/amounts.py` | 금액 계산(Decimal) |
| `sap_po/frames.py` | 응답 → 화면 표 |
| `sap_po/sample.py` | SAP 없이 쓰는 가짜 OData 서버 |
| `scripts/inspect_service.py` | 서비스 필드 확인 |
| `.streamlit/config.toml` | 주소 `127.0.0.1`, 포트 1637 |
