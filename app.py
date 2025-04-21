import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
import plotly.express as px
import os

# 페이지 설정
st.set_page_config(page_title="토계부", layout="wide")

# 다크모드 전용 스타일
st.markdown('<style>body, .stApp { background-color: #111111; color: white; }</style>', unsafe_allow_html=True)

# Firebase 인증을 secrets.toml에서 읽어옵니다.
cred = credentials.Certificate({
    "type": st.secrets["firebase"]["type"],
    "project_id": st.secrets["firebase"]["project_id"],
    "private_key_id": st.secrets["firebase"]["private_key_id"],
    "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),  # \\n을 \n으로 변환
    "client_email": st.secrets["firebase"]["client_email"],
    "client_id": st.secrets["firebase"]["client_id"],
    "auth_uri": st.secrets["firebase"]["auth_uri"],
    "token_uri": st.secrets["firebase"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
})

# Firebase 초기화
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://toto-ff3f5-default-rtdb.firebaseio.com/'
    })

ref = db.reference('tokeibu_records')

# 제목 + 통계
col_title, col_summary = st.columns([2.2, 1.8])
with col_title:
    st.title("괴굉민과 괴성호의 토계부")

# 날짜 필터링
st.sidebar.subheader("조회 기간 설정")
start_date = st.sidebar.date_input("📅 집계 시작일", datetime.today().replace(day=1))
end_date = st.sidebar.date_input("📅 집계 종료일", datetime.today())

# 누적 수익 그래프
all_data = ref.get()
df_all = pd.DataFrame(all_data.values()) if all_data else pd.DataFrame()
if not df_all.empty:
    df_all['날짜'] = pd.to_datetime(df_all['날짜'])
    df_all.sort_values('날짜', inplace=True)
    df_all['누적 수익'] = df_all['수익'].cumsum()
    fig = px.line(df_all, x='날짜', y='누적 수익', markers=True)
    fig.update_layout(title='누적 수익 추이', height=300, margin=dict(l=10, r=10, t=30, b=10))
    fig.update_xaxes(tickformat="%Y-%m-%d")
    fig.update_yaxes(tickformat=".1f")
    fig.update_traces(line=dict(width=2), hovertemplate='날짜: %{x}<br>누적 수익: %{y:.1f}')
    st.sidebar.plotly_chart(fig, use_container_width=True)

# 입력 폼
st.subheader("배팅 정보 입력")
date = st.date_input("날짜", datetime.today())
match = st.text_input("경기 정보")
amount = st.number_input("배팅금액", step=1000)
odds = st.number_input("배당률", step=0.01)
result = st.selectbox("결과", ["적중", "미적중", "대기"])

if st.button("기록 추가"):
    if result == "적중":
        profit = int(amount * odds - amount)
    elif result == "미적중":
        profit = -int(amount)
    else:
        profit = 0
    record = {
        "날짜": date.strftime("%Y-%m-%d"),
        "경기": match,
        "배팅금": int(amount),
        "배당률": float(odds),
        "결과": result,
        "수익": int(profit)
    }
    ref.push(record)
    st.rerun()

# 데이터 불러오기 및 출력
data = ref.get()
if data:
    df = pd.DataFrame(data.values())
    df['firebase_key'] = list(data.keys())
    df['날짜'] = pd.to_datetime(df['날짜'])
    df.sort_values('날짜', inplace=True)
    df_filtered = df[(df['날짜'] >= pd.to_datetime(start_date)) & (df['날짜'] <= pd.to_datetime(end_date))].copy()

    # 통계 출력 (줄바꿈 형식)
    wins = df_filtered[df_filtered['결과'] == '적중'].shape[0]
    total = df_filtered[df_filtered['결과'].isin(['적중', '미적중'])].shape[0]
    roi_total = df_filtered['수익'].sum()
    roi = roi_total / df_filtered['배팅금'].sum() * 100 if df_filtered['배팅금'].sum() > 0 else 0
    acc_rate = f"{(wins/total)*100:.1f}%" if total > 0 else "0.0%"
    with col_summary:
        st.markdown(f"### 📊 수익률: {'+' if roi_total >=0 else ''}{roi_total:,}원")
        st.markdown(f"### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;승률: {acc_rate}")

    # 표 출력
    st.subheader("전체 배팅 기록")
    df_display = df_filtered.drop(columns=['firebase_key']).copy()
    df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')
    for col in ['배팅금', '수익']:
        df_display[col] = df_display[col].apply(lambda x: f"{x:,}")
    st.dataframe(df_display, use_container_width=True)

    # 수정 영역
    st.subheader("🛠 선택한 기록 수정/삭제")
    clicked = st.radio("수정할 경기 선택", df_filtered.index, format_func=lambda x: f"{df_filtered.loc[x, '경기']} ({df_filtered.loc[x, '날짜'].strftime('%Y-%m-%d')})")

    if clicked is not None:
        row = df_filtered.loc[clicked]
        new_date = st.date_input("일자", row['날짜'], key='edit_date')
        new_match = st.text_input("메모 [선택입력]", row['경기'], key='edit_match')
        new_amount = st.number_input("구매금액", value=row['배팅금'], step=1000, key='edit_amount')
        new_odds = st.number_input("배당", value=row['배당률'], step=0.01, key='edit_odds')
        try:
            new_result = st.radio("적중 / 미적중 / 대기", ["적중", "미적중", "대기"], index=["적중", "미적중", "대기"].index(row['결과']), key='edit_result')
        except:
            new_result = st.radio("적중 / 미적중 / 대기", ["적중", "미적중", "대기"], key='edit_result')

        expected = int(new_amount * new_odds) if new_result == "적중" else -int(new_amount) if new_result == "미적중" else 0
        st.markdown(f"**당첨금액:** {expected:,}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("수정"):
                ref.child(df_filtered.loc[clicked, 'firebase_key']).update({
                    "날짜": new_date.strftime("%Y-%m-%d"),
                    "경기": new_match,
                    "배팅금": int(new_amount),
                    "배당률": float(new_odds),
                    "결과": new_result,
                    "수익": int(expected)
                })
                st.rerun()
        with col2:
            if st.button("삭제"):
                ref.child(df_filtered.loc[clicked, 'firebase_key']).delete()
                st.rerun()
        with col3:
            st.info("다른 항목 선택 시 자동 취소됩니다.")
