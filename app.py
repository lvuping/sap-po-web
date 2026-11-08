"""SAP 구매오더 웹 — SAP S/4HANA 표준 구매오더 API(OData V4)를 읽어 보여 주는 Streamlit 화면.

실행: uv run streamlit run app.py --server.address 127.0.0.1 --server.port 1637
환경변수
  SAP_PO_WEB_SOURCE  sap(기본) | sample(지어낸 예시 데이터, SAP 에 연결하지 않음)
  SAP_PO_WEB_HOST    https://<호스트>:<포트>  — 있으면 화면에 주소 칸을 띄우지 않는다
  SAP_PO_WEB_CLIENT  기본 400
  SAP_PO_WEB_USER    사용자 기본값
  SAP_PO_WEB_LABEL   화면에 보일 시스템 이름(예: T41)
비밀번호는 화면에서만 받는다. 파일·환경변수에 두지 않는다.
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from sap_po import (
    SERVICE_PATH,
    Connection,
    PoFilter,
    PurchaseOrderApi,
    RequestLog,
    SapApiError,
    build_base_url,
)
from sap_po.frames import header_pairs, headers_frame, item_rows, items_frame
from sap_po.sample import SampleService

SAMPLE = os.environ.get("SAP_PO_WEB_SOURCE", "sap").lower() == "sample"
ENV_HOST = os.environ.get("SAP_PO_WEB_HOST", "").strip()
LABEL = os.environ.get("SAP_PO_WEB_LABEL", "").strip()

DIAGRAM = """
digraph G {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#f3f6fa", color="#9aa8b8", fontname="sans-serif", fontsize=12, margin="0.25,0.12"];
  edge [color="#5b6b7d", fontname="sans-serif", fontsize=10];
  b [label="브라우저\\n(이 화면)"];
  a [label="Python 웹 앱\\nStreamlit · httpx"];
  g [label="SAP Gateway\\nOData V4"];
  s [label="SAP S/4HANA\\n표준 구매오더"];
  b -> a [label="127.0.0.1"];
  a -> g [label="HTTPS GET"];
  g -> s [label="api_purchaseorder_2"];
}
"""

CHART_HEIGHT = 300  # 원격 PC 화면(약 1900×930)에서 KPI 와 차트 두 개가 한 화면에 들도록

st.set_page_config(page_title="SAP 구매오더 웹", layout="wide")
# 기본 위쪽 여백(6rem)을 줄여 표와 차트가 스크롤 없이 더 보이게 한다
st.markdown(
    '<style>[data-testid="stMainBlockContainer"]{padding-top:2rem}</style>',
    unsafe_allow_html=True,
)
ss = st.session_state
ss.setdefault("requests", [])
ss.setdefault("api", None)
ss.setdefault("nb_total", None)
ss.setdefault("orders", None)
ss.setdefault("order", None)
ss.setdefault("dash", None)
ss.setdefault("filter", PoFilter())
ss.setdefault("selected_po", "")


def remember(entry: RequestLog, book: list[RequestLog] = ss.requests) -> None:
    """화면 '연결 구조' 탭에 보일 최근 요청 50개. 인증 정보는 들어 있지 않다."""
    book.insert(0, entry)
    del book[50:]


def connect(host: str, client: str, user: str, password: str) -> None:
    if not (host and client and user and password):
        st.sidebar.error("서버 주소 · 클라이언트 · 사용자 · 비밀번호를 모두 넣으세요.")
        return
    try:
        conn = Connection(build_base_url(host), client.strip(), user.strip().upper(), LABEL)
    except ValueError as exc:
        st.sidebar.error(str(exc))
        return
    api = PurchaseOrderApi(conn, password, on_request=remember)
    try:
        total = api.count(PoFilter())
    except SapApiError as exc:
        api.close()
        st.sidebar.error(str(exc))
        return
    ss.api, ss.nb_total = api, total
    st.rerun()


def bar(frame: pd.DataFrame, x: str, y: str, title: str, **kwargs: str):
    """막대 차트. 코드값은 숫자가 아니라 이름으로, 축 제목은 빼고(세로 한글이 눕는다) 단위는 제목에."""
    fig = px.bar(frame, x=x, y=y, title=title, height=CHART_HEIGHT, **kwargs)
    fig.update_xaxes(type="category", title=None).update_yaxes(title=None)
    return fig.update_layout(margin={"t": 48, "b": 8, "l": 8, "r": 8})


def disconnect() -> None:
    if ss.api is not None:
        ss.api.close()
    for key in ("api", "nb_total", "orders", "order", "dash"):
        ss[key] = None
    ss.requests.clear()


if SAMPLE and ss.api is None:
    sample = SampleService()
    ss.api = PurchaseOrderApi(
        Connection("https://sample.invalid" + SERVICE_PATH, "400", "SAMPLE", "예시 데이터"),
        None,
        transport=sample.transport(),
        on_request=remember,
    )
    ss.nb_total = ss.api.count(PoFilter())

# 왼쪽: 연결
with st.sidebar:
    st.header("SAP 연결")
    if SAMPLE:
        st.warning("예시 데이터 모드 — 지어낸 데이터입니다. SAP 에 연결하지 않습니다.")
    elif ss.api is None:
        with st.form("connect", clear_on_submit=True):
            if ENV_HOST:
                st.caption(f"서버: {LABEL or '환경변수 SAP_PO_WEB_HOST'}")
                host = ENV_HOST
            else:
                host = st.text_input("서버 주소", placeholder="https://호스트:포트")
            client = st.text_input("클라이언트", value=os.environ.get("SAP_PO_WEB_CLIENT", "400"), max_chars=3)
            user = st.text_input("사용자", value=os.environ.get("SAP_PO_WEB_USER", ""))
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("연결", type="primary")
        if submitted:
            connect(host, client, user, password)
    if ss.api is not None:
        conn = ss.api.conn  # 좁은 사이드바에서 사용자 이름이 끊기지 않게 두 줄로
        st.success(f"**연결됨** · {conn.label or 'SAP'}  \nclient {conn.client} · {conn.user}")
        st.caption(f"표준 구매오더(NB) {ss.nb_total:,}건")
        if not SAMPLE and st.button("연결 끊기"):
            disconnect()
            st.rerun()

st.title("SAP 구매오더 웹")
st.caption("SAP S/4HANA 표준 API(OData V4 · api_purchaseorder_2)로 구매오더를 읽어 보여 줍니다. 읽기 전용입니다.")
if ss.api is None:
    st.info("왼쪽에서 SAP 에 연결하세요.")
    st.stop()

api: PurchaseOrderApi = ss.api
tab_list, tab_detail, tab_dash, tab_how = st.tabs(["구매오더 목록", "구매오더 상세", "대시보드", "연결 구조"])

with tab_list:
    with st.form("search"):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1.3, 1.2, 1.2])
        order_type = c1.text_input("문서유형", value=ss.filter.order_type)
        company = c2.text_input("회사코드", value=ss.filter.company_code)
        supplier = c3.text_input("공급업체", value=ss.filter.supplier)
        date_from = c4.date_input("발주일 부터", value=ss.filter.date_from, format="YYYY-MM-DD")
        date_to = c5.date_input("발주일 까지", value=ss.filter.date_to, format="YYYY-MM-DD")
        search = st.form_submit_button("조회", type="primary")
    if search:
        try:
            flt = PoFilter(order_type, company, supplier, date_from, date_to)
            flt.expression()  # 입력 검사
            ss.orders = (api.count(flt), api.list_orders(flt, limit=200))
            ss.filter, ss.dash = flt, None
        except (ValueError, SapApiError) as exc:
            st.error(str(exc))
    if ss.orders:
        total, rows = ss.orders
        st.metric("조건에 맞는 구매오더", f"{total:,}건")
        if total > len(rows):
            st.caption(f"앞 {len(rows):,}건만 보여 줍니다.")
        table = headers_frame(rows)
        picked = st.dataframe(
            table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="po_table"
        )
        if picked.selection.rows:
            ss.selected_po = table.iloc[picked.selection.rows[0]]["구매오더"]
            st.caption(f"{ss.selected_po} 을(를) 골랐습니다. '구매오더 상세' 탭에서 봅니다.")

with tab_detail:
    with st.form("detail"):
        c1, c2, _ = st.columns([2, 1, 5], vertical_alignment="bottom")
        number = c1.text_input("구매오더 번호", value=ss.selected_po, max_chars=10)
        with c2:
            load = st.form_submit_button("불러오기", type="primary")
    if load:
        try:
            ss.order = api.order(number)
        except (ValueError, SapApiError) as exc:
            st.error(str(exc))
    if ss.order:
        order = ss.order
        st.subheader(f"구매오더 {order.get('PurchaseOrder', '')}")
        left, right = st.columns([1, 2])
        left.dataframe(header_pairs(order), hide_index=True, width="stretch")
        items = items_frame(order)
        right.markdown(f"**품목 {len(items)}개**")
        right.dataframe(items, hide_index=True, width="stretch")

with tab_dash:
    st.caption("목록 탭의 조건으로 품목까지 불러와 집계합니다(구매오더 최대 500건).")
    if st.button("SAP 에서 불러와 집계", type="primary"):
        try:
            ss.dash = api.orders_with_items(ss.filter, limit=500)
        except SapApiError as exc:
            st.error(str(exc))
    if ss.dash is not None:
        lines = item_rows(ss.dash)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("구매오더", f"{len(ss.dash):,}")
        k2.metric("품목", f"{len(lines):,}")
        k3.metric("공급업체", f"{lines['공급업체'].nunique():,}")
        by_cur = lines.groupby("통화")["순금액"].sum().sort_values(ascending=False)
        if not by_cur.empty:
            k4.metric(f"순금액 ({by_cur.index[0]})", f"{by_cur.iloc[0]:,.2f}")
            if len(by_cur) > 1:
                k4.caption(" · ".join(f"{cur} {amt:,.2f}" for cur, amt in by_cur.iloc[1:].items()))
        heads = pd.DataFrame(
            [{"회사코드": o.get("CompanyCode", ""), "월": str(o.get("PurchaseOrderDate", ""))[:7]} for o in ss.dash]
        )
        g1, g2 = st.columns(2)
        per_company = heads.groupby("회사코드").size().reset_index(name="구매오더 수")
        g1.plotly_chart(bar(per_company, "회사코드", "구매오더 수", "회사코드별 구매오더 (건)"), width="stretch")
        top = (
            lines.groupby(["공급업체", "통화"])["순금액"].sum().reset_index().sort_values("순금액", ascending=False).head(10)
        )
        g2.plotly_chart(bar(top, "공급업체", "순금액", "공급업체별 순금액 상위 10", color="통화"), width="stretch")
        per_month = heads.groupby("월").size().reset_index(name="구매오더 수")
        st.plotly_chart(bar(per_month, "월", "구매오더 수", "월별 구매오더 (건)"), width="stretch")
        st.caption("순금액 = 순단가 × 수량 ÷ 가격단위의 통화별 합계입니다. 환율은 적용하지 않습니다.")

with tab_how:
    st.graphviz_chart(DIAGRAM, width="stretch")
    st.markdown(
        "- 화면과 Python 앱은 같은 PC 에서 돕니다. SAP 에는 앱만 붙습니다.\n"
        "- SAP 표준 API(OData V4)를 HTTPS GET 으로 부릅니다. 같은 코드가 주소와 계정만 바꾸면 다른 S/4HANA 에서도 돕니다.\n"
        "- 비밀번호는 이 화면의 메모리에만 있고 파일 · 로그에 남지 않습니다."
    )
    st.subheader("방금 보낸 요청")
    if ss.requests:
        st.dataframe(
            pd.DataFrame(
                [
                    {"시각": r.at, "메서드": r.method, "경로": r.path, "상태": r.status, "ms": r.millis}
                    for r in ss.requests
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("아직 보낸 요청이 없습니다.")
