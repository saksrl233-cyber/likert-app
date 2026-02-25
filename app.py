import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Likert Crosstab", layout="wide")

LIKERT_MAP_JP = {
    1: "とても当てはまる",
    2: "やや当てはまる",
    3: "どちらともいえない",
    4: "あまり当てはまらない",
    5: "まったく当てはまらない",
}

DEFAULT_ORDER = [
    "とても当てはまる",
    "やや当てはまる",
    "どちらともいえない",
    "あまり当てはまらない",
    "まったく当てはまらない",
]


def read_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    raise ValueError("CSV 또는 Excel(xlsx/xls)만 지원합니다.")


def normalize_likert_series(s: pd.Series) -> pd.Series:
    """
    입력이 1~5 숫자 or '1'~'5' 문자열 or 일본어 라벨(とても当てはまる 등)이어도
    최종적으로 일본어 라벨로 통일해줌.
    """
    # 숫자처럼 보이면 숫자로 변환
    s2 = pd.to_numeric(s, errors="ignore")

    # 숫자/숫자문자(1~5) -> 라벨
    if pd.api.types.is_numeric_dtype(s2):
        return s2.map(LIKERT_MAP_JP).astype("string")

    # 문자열 처리
    s_str = s.astype("string").str.strip()

    # '1'~'5' -> 라벨
    as_num = pd.to_numeric(s_str, errors="coerce")
    if as_num.notna().any():
        s_mixed = s_str.copy()
        mask = as_num.notna()
        s_mixed.loc[mask] = as_num.loc[mask].map(LIKERT_MAP_JP)
        return s_mixed

    # 이미 라벨로 들어온 경우(일본어) 그대로
    return s_str


def build_likert_table(df: pd.DataFrame, q_col: str, seg_col: str | None, seg_values: list[str] | None):
    work = df.copy()

    # 응답 라벨 통일
    work[q_col] = normalize_likert_series(work[q_col])

    # 결측 제거
    work = work[work[q_col].notna()]

    rows = []

    # 전체(GT)
    gt = work[q_col].value_counts(dropna=False)
    gt_n = int(gt.sum())
    for cat in DEFAULT_ORDER:
        rows.append({"세그먼트": f"전체 (GT) (N={gt_n})", "응답": cat, "비율": 100 * (gt.get(cat, 0) / gt_n if gt_n else 0)})

    # 세그먼트별
    if seg_col:
        if seg_values:
            work = work[work[seg_col].astype("string").isin(seg_values)]

        for seg_name, sub in work.groupby(work[seg_col].astype("string"), dropna=False):
            vc = sub[q_col].value_counts(dropna=False)
            n = int(vc.sum())
            label = f"{seg_name} (N={n})"
            for cat in DEFAULT_ORDER:
                rows.append({"세그먼트": label, "응답": cat, "비율": 100 * (vc.get(cat, 0) / n if n else 0)})

    out = pd.DataFrame(rows)
    # 0에 가까운 값은 표시 깔끔하게
    out["비율"] = out["비율"].round(0)
    return out


st.title("로우데이터 → 리커트(5점) 결과(100% 누적 막대) 자동 생성")

with st.sidebar:
    st.header("1) 파일 업로드")
    uploaded = st.file_uploader("CSV 또는 Excel 업로드", type=["csv", "xlsx", "xls"])

    st.header("2) 설정")
    # 파일 업로드 전에는 빈 설정
    if uploaded is None:
        st.info("왼쪽에서 파일을 업로드하세요.")
        st.stop()

df = read_file(uploaded)

st.subheader("업로드 데이터 미리보기")
st.dataframe(df.head(30), use_container_width=True)

st.markdown("---")
st.subheader("문항/세그먼트 선택")

# Q 컬럼 자동 추천: Q로 시작하는 컬럼
cols = list(df.columns)
q_candidates = [c for c in cols if str(c).upper().startswith("Q")]
q_col = st.selectbox("리커트 5점 문항 컬럼 선택", options=q_candidates if q_candidates else cols)

seg_col = st.selectbox("세그먼트(그룹) 컬럼 선택 (없으면 '없음')", options=["없음"] + cols)

seg_values = None
if seg_col != "없음":
    seg_series = df[seg_col].astype("string")
    unique_vals = sorted(seg_series.dropna().unique().tolist())
    seg_values = st.multiselect("표시할 세그먼트 값(선택 안 하면 전체 표시)", options=unique_vals, default=unique_vals[:min(6, len(unique_vals))])

tab = build_likert_table(df, q_col=q_col, seg_col=None if seg_col == "없음" else seg_col, seg_values=seg_values)

st.markdown("---")
st.subheader("결과 테이블(%)")
st.dataframe(tab, use_container_width=True)

st.subheader("그래프(가로 100% 누적 막대)")

# Plotly
fig = px.bar(
    tab,
    x="비율",
    y="세그먼트",
    color="응답",
    orientation="h",
    category_orders={"응답": DEFAULT_ORDER},
    text="비율",
)
fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
fig.update_layout(
    barmode="stack",
    xaxis_title="%",
    yaxis_title="",
    legend_title="",
    xaxis=dict(range=[0, 100]),
    height=max(420, 70 * tab["세그먼트"].nunique()),
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "입력값이 1~5(또는 '1'~'5')면 자동으로 일본어 라벨(とても当てはまる… 등)로 변환합니다. "
    "이미 라벨로 들어있어도 그대로 사용합니다."
)