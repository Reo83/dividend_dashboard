import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import platform
import matplotlib.font_manager as fm
import io # BytesIO를 위해 추가

# --- 로그인 정보 설정 (Streamlit Secrets 사용) ---
# Streamlit Cloud에 배포 시에는 'Secrets'에 설정된 값이 사용됩니다.
# 로컬에서 테스트할 때는 'your_username', 'your_password' 값을 변경하여 사용하세요.
USERNAME = st.secrets.get("app_credentials", {}).get("username", "your_username")
PASSWORD = st.secrets.get("app_credentials", {}).get("password", "your_password")

# --- 로그인 기능 ---
def check_password():
    """Returns `True` if the user enters the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if (st.session_state.get("username") == USERNAME and
                st.session_state.get("password") == PASSWORD):
            st.session_state["password_correct"] = True
            st.session_state["show_app"] = True # 로그인 성공 시 앱 표시
            # del st.session_state["password"]  # 보안을 위해 비밀번호 세션에서 삭제
            st.success("로그인 성공!")
        else:
            st.session_state["password_correct"] = False
            st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")

    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        st.session_state["show_app"] = False # 기본적으로 앱 숨김

    if not st.session_state["password_correct"]:
        st.title("로그인이 필요합니다")
        st.text_input("사용자 이름", key="username")
        st.text_input("비밀번호", type="password", key="password", on_change=password_entered)
        st.button("로그인", on_click=password_entered) # 버튼 클릭 시에도 실행되도록 추가
        st.stop() # 로그인 성공 전까지 앱 내용 표시 중지
    else:
        return True

# --- 앱의 실제 내용 (로그인 성공 시에만 실행) ---
if check_password(): # 이 문장 아래의 모든 앱 코드는 로그인 성공 시에만 실행됩니다.

    # [1] 한글 폰트 설정 (OS별 자동 적용)
    # Streamlit Cloud 환경을 고려하여 폰트 설정 방식을 약간 조정합니다.
    try:
        if platform.system() == 'Windows':
            font_path = "C:/Windows/Fonts/malgun.ttf"
            font_name = fm.FontProperties(fname=font_path).get_name()
            plt.rc("font", family=font_name)
        elif platform.system() == 'Darwin':  # macOS
            font_path = "/System/Library/Fonts/AppleGothic.ttf"
            font_name = fm.FontProperties(fname=font_path).get_name()
            plt.rc("font", family=font_name)
        else:  # Linux (Streamlit Cloud는 주로 Linux 기반)
            # Streamlit Cloud에서는 기본 폰트를 사용하도록 설정
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = ["DejaVu Sans"] # 또는 다른 sans-serif 폰트
            st.warning("⚠️ Linux 환경 (Streamlit Cloud)에서는 기본 폰트가 사용됩니다. 한글 표시가 다를 수 있습니다.")

        plt.rcParams["axes.unicode_minus"] = False # 음수 부호 깨짐 방지
    except Exception as e:
        st.warning(f"⚠️ 폰트 설정 중 오류 발생: {e}. 기본 폰트로 표시됩니다.")
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False


    st.set_page_config(layout="wide") # 페이지 레이아웃을 넓게 설정

    st.title("💰 배당금 분석 대시보드")
    st.markdown("엑셀 파일을 업로드하여 배당금 내역을 분석하고 시각화합니다.")

    # [2] 사용자 파일 선택 -> Streamlit의 file_uploader로 변경
    uploaded_file = st.file_uploader("배당 거래내역 엑셀 파일을 선택하세요", type=["xlsx", "xls"])

    df_div = pd.DataFrame() # 전역 변수로 df_div 선언

    if uploaded_file is not None:
        try:
            # BytesIO를 사용하여 메모리에서 파일 읽기
            xls = pd.ExcelFile(io.BytesIO(uploaded_file.getvalue()))
            sheet_names = xls.sheet_names
            
            # [3] 엑셀 파일 읽기 및 시트 병합
            df_all = pd.concat(
                [xls.parse(sheet).assign(연도=int(sheet)) for sheet in sheet_names],
                ignore_index=True
            )

            # [4] 날짜 처리 및 배당 필터링
            df_all["거래일자"] = pd.to_datetime(df_all["거래일자"], errors='coerce')
            div_keywords = ["배당금외화입금", "배당금입금", "ETF분배금입금", "현금배당", "ETF/상장클래스 분배금입금"]
            df_div = df_all[df_all["거래종류"].isin(div_keywords)].copy()

            # [5] 결측값 처리 및 배당금 계산
            df_div["제세금합"] = df_div["제세금합"].fillna(0)
            df_div["단가"] = df_div["단가"].fillna(1)
            df_div["통화코드"] = df_div["통화코드"].fillna("KRW")
            df_div["배당금(세전)"] = 0.0
            df_div["배당금(세후)"] = 0.0

            mask_us = df_div["통화코드"] == "USD"
            df_div.loc[mask_us, "배당금(세전)"] = df_div.loc[mask_us, "외화거래금액"] * df_div.loc[mask_us, "단가"]
            df_div.loc[mask_us, "배당금(세후)"] = (df_div.loc[mask_us, "외화거래금액"] - df_div.loc[mask_us, "제세금합"]) * df_div.loc[mask_us, "단가"]

            mask_kr = df_div["통화코드"] != "USD"
            df_div.loc[mask_kr, "배당금(세전)"] = df_div.loc[mask_kr, "거래금액"]
            df_div.loc[mask_kr, "배당금(세후)"] = df_div.loc[mask_kr, "거래금액"] - df_div.loc[mask_kr, "제세금합"]

            df_div["배당금(세후)"] = df_div["배당금(세후)"].clip(lower=0).fillna(0)

            # [6] 연도/월 컬럼 생성
            df_div["연도"] = df_div["거래일자"].dt.year
            df_div["월"] = df_div["거래일자"].dt.month

            st.success("✅ 파일이 성공적으로 업로드 및 처리되었습니다!")

            # --- 대시보드 탭 구성 ---
            tab1, tab2, tab3, tab4 = st.tabs(["월별 배당 차트", "연도별 배당 달력", "계좌별/월별 상세", "FIRE 현황"])

            with tab1:
                st.header("📈 연도별 월별 배당금 차트")
                if not df_div.empty:
                    monthly_data = df_div.groupby(['연도', '월'])[['배당금(세전)', '배당금(세후)']].sum().reset_index()
                    monthly_data[['배당금(세전)', '배당금(세후)']] = monthly_data[['배당금(세전)', '배당금(세후)']].round().astype(int)

                    years = sorted(monthly_data['연도'].unique(), reverse=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        selected_year_chart = st.selectbox('차트 연도 선택:', years, index=0, key='chart_year_select')
                    with col2:
                        dividend_type_chart = st.radio('차트 금액 기준:', ['배당금(세전)', '배당금(세후)'], key='chart_type_select')

                    # 12개월 템플릿 생성
                    full_months = pd.DataFrame({'월': range(1, 13)})

                    # 해당 연도 데이터 가져오고 1~12월로 merge
                    df_plot = full_months.merge(
                        monthly_data[monthly_data['연도'] == selected_year_chart][['월', dividend_type_chart]],
                        on='월', how='left').fillna(0)

                    # 월 이름 라벨 생성
                    month_labels = [f"{m}월" for m in df_plot['월']]

                    bars = go.Bar(
                        x=month_labels,
                        y=df_plot[dividend_type_chart],
                        text=[f"{int(v):,}원" if v > 0 else "" for v in df_plot[dividend_type_chart]],
                        textposition='outside',
                        marker_color='orange',
                        name=dividend_type_chart
                    )

                    total = df_plot[dividend_type_chart].sum()

                    layout = go.Layout(
                        title=f"{selected_year_chart}년 {dividend_type_chart} (총합: {int(total):,}원)",
                        yaxis=dict(title='금액 (원)', tickformat=","),  # 천단위 , 표시
                        xaxis=dict(title='월', tickmode='array', tickvals=list(range(12)), ticktext=month_labels),
                        plot_bgcolor='black',
                        paper_bgcolor='black',
                        font=dict(color='white'),
                        height=500
                    )

                    fig = go.Figure(data=[bars], layout=layout)
                    fig.update_traces(marker_line_color='black', marker_line_width=1.5)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("차트를 표시할 데이터가 없습니다.")

            with tab2:
                st.header("📅 연도별 배당 달력")

                # 기존: 종목별 배당 달력 (유지)
                def create_stock_dividend_calendar(df, year, dividend_type='배당금(세후)', account_name=None):
                    df_filtered = df[df['연도'] == year]
                    if account_name and account_name != '전체 계좌': # '전체 계좌' 선택 시 필터링하지 않음
                        df_filtered = df_filtered[df_filtered['계좌'] == account_name]

                    df_pivot = df_filtered.pivot_table(index='종목명', columns='월', values=dividend_type, aggfunc='sum', fill_value=0)
                    df_pivot = df_pivot.reindex(columns=range(1, 13), fill_value=0)  # 1~12월 보장

                    df_pivot['총합'] = df_pivot.sum(axis=1)
                    total_row = df_pivot.sum(axis=0).to_frame().T
                    total_row.index = ['총합']
                    df_final = pd.concat([df_pivot, total_row])
                    return df_final.round(0).astype(int)

                # 새로 추가: 계좌별 월별 배당 달력
                def create_account_monthly_calendar(df, year, dividend_type='배당금(세후)', account_name=None):
                    df_filtered = df[df['연도'] == year]
                    if account_name and account_name != '전체 계좌':
                        df_filtered = df_filtered[df_filtered['계좌'] == account_name]
                    
                    if df_filtered.empty:
                        return pd.DataFrame()

                    # '계좌'를 행으로, '월'을 열로 하는 피벗 테이블 생성
                    df_pivot = df_filtered.groupby(['계좌', '월'])[dividend_type].sum().unstack(level='월', fill_value=0)
                    df_pivot = df_pivot.reindex(columns=range(1, 13), fill_value=0) # 1~12월 보장
                    
                    df_pivot['총합'] = df_pivot.sum(axis=1) # 계좌별 총합
                    
                    # 전체 총합 행 추가
                    total_row = df_pivot.sum(axis=0).to_frame().T
                    total_row.index = ['전체 총합']
                    df_final = pd.concat([df_pivot, total_row])
                    
                    return df_final.round(0).astype(int)


                if not df_div.empty:
                    years_calendar = sorted(df_div['연도'].unique(), reverse=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        selected_year_calendar = st.selectbox('달력 연도 선택:', years_calendar, index=0, key='calendar_year_select')
                    with col2:
                        dividend_type_calendar = st.radio('달력 금액 기준:', ['배당금(세전)', '배당금(세후)'], key='calendar_type_select')
                    with col3:
                        all_accounts = ['전체 계좌'] + sorted(df_div['계좌'].unique().tolist())
                        selected_account_calendar = st.selectbox('계좌 선택:', all_accounts, key='account_calendar_select')

                    # --- 기존: 종목별 배당 달력 ---
                    st.subheader(f"--- {selected_year_calendar}년 {selected_account_calendar} 종목별 배당 달력 ---")
                    df_stock_calendar = create_stock_dividend_calendar(df_div, selected_year_calendar, dividend_type_calendar, selected_account_calendar)

                    if df_stock_calendar.empty:
                        st.info(f"{selected_year_calendar}년 {selected_account_calendar}에 해당하는 종목별 배당 데이터가 없습니다.")
                    else:
                        st.dataframe(
                            df_stock_calendar.style.apply(lambda x: ['font-weight: bold' if x.name == '총합' else '' for i in x], axis=1)
                            .format(lambda x: f"{x:,.0f}" if x != 0 else ""),
                            use_container_width=True
                        )
                    
                    st.markdown("---") # 구분선 추가

                    # --- 새로 추가: 계좌별 월별 배당 달력 ---
                    st.subheader(f"--- {selected_year_calendar}년 {selected_account_calendar} 계좌별 월별 배당 달력 ---")
                    df_account_calendar = create_account_monthly_calendar(df_div, selected_year_calendar, dividend_type_calendar, selected_account_calendar)

                    if df_account_calendar.empty:
                        st.info(f"{selected_year_calendar}년 {selected_account_calendar}에 해당하는 계좌별 배당 데이터가 없습니다.")
                    else:
                        st.dataframe(
                            df_account_calendar.style.apply(lambda x: ['font-weight: bold' if x.name == '전체 총합' else '' for i in x], axis=1)
                            .format(lambda x: f"{x:,.0f}" if x != 0 else ""),
                            use_container_width=True
                        )

                else:
                    st.info("달력을 표시할 데이터가 없습니다.")

            with tab3:
                st.header("📊 계좌별/월별 상세 배당 내역")

                # get_dividend_summary_for_selection 함수: 계좌별 월별 요약 테이블 생성
                def get_dividend_summary_for_selection(df, owner_name, account_names, selected_year, dividend_type='배당금(세후)'):
                    if not account_names:
                        return pd.DataFrame()
                    df_filtered = df[(df['소유주'] == owner_name) & (df['계좌'].isin(account_names)) & (df['연도'] == selected_year)].copy()
                    if df_filtered.empty:
                        return pd.DataFrame()
                    
                    # '계좌'를 행으로, '월'을 열로 하는 피벗 테이블 생성
                    summary = df_filtered.groupby(['계좌', '월'])[dividend_type].sum().unstack(level='월', fill_value=0)
                    summary = summary.reindex(columns=range(1, 13), fill_value=0) # 1~12월 보장
                    summary['총합'] = summary.sum(axis=1) # 계좌별 총합
                    
                    # 전체 총합 행 추가
                    total_row = summary.sum(axis=0).to_frame().T
                    total_row.index = ['전체 총합']
                    df_final = pd.concat([summary, total_row])
                    
                    return df_final.round(0).astype(int)

                def get_monthly_details_for_selection(df, owner_name, account_names, selected_year, selected_month, dividend_type='배당금(세후)'):
                    if not account_names:
                        return pd.DataFrame()
                    df_filtered = df[
                        (df['소유주'] == owner_name) &
                        (df['계좌'].isin(account_names)) &
                        (df['연도'] == selected_year) &
                        (df['월'] == selected_month)
                    ].copy()
                    if df_filtered.empty:
                        return pd.DataFrame()
                    details = df_filtered[['거래일자', '계좌', '종목명', '통화코드', '배당금(세전)', '제세금합', '배당금(세후)']].sort_values(by='거래일자', ascending=False)
                    details['거래일자'] = details['거래일자'].dt.strftime('%Y-%m-%d')
                    total_row = pd.DataFrame({
                        '거래일자': ['총합'], '계좌': [''], '종목명': [''], '통화코드': [''],
                        '배당금(세전)': [details['배당금(세전)'].sum()],
                        '제세금합': [details['제세금합'].sum()],
                        '배당금(세후)': [details['배당금(세후)'].sum()]
                    })
                    details_final = pd.concat([details, total_row], ignore_index=True)
                    return details_final.round(0).astype({col: int for col in ['배당금(세전)', '제세금합', '배당금(세후)']})


                if not df_div.empty:
                    if '소유주' not in df_div.columns:
                        st.warning("⚠️ '소유주' 컬럼이 데이터에 없습니다. 엑셀 파일에 '소유주' 컬럼을 확인해주세요.")
                        owners = []
                    else:
                        owners = sorted(df_div['소유주'].unique().tolist())

                    years_account = sorted(df_div['연도'].unique().tolist(), reverse=True)
                    months_account = list(range(1, 13))

                    if not owners:
                        st.info("선택할 수 있는 소유주가 없습니다.")
                    elif not years_account:
                        st.info("선택할 수 있는 연도가 없습니다.")
                    else:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            selected_owner = st.selectbox('소유주 선택:', owners, key='owner_select')
                        
                        # 소유주 선택에 따라 계좌 목록 업데이트
                        filtered_accounts = []
                        if selected_owner:
                            filtered_accounts = sorted(df_div[df_div['소유주'] == selected_owner]['계좌'].unique().tolist())
                        
                        with col2:
                            selected_accounts = st.multiselect(
                                '계좌 선택 (다중 선택 가능):',
                                options=filtered_accounts,
                                default=filtered_accounts, # 기본적으로 모든 계좌 선택
                                key='account_select'
                            )
                        with col3:
                            selected_year_account = st.selectbox('연도 선택:', years_account, key='year_account_select')
                        with col4:
                            selected_month_account = st.selectbox('월 선택:', months_account, key='month_account_select')
                        
                        dividend_type_account = st.radio('금액 기준:', ['배당금(세전)', '배당금(세후)'], key='type_account_select')

                        if selected_owner and selected_accounts and selected_year_account: # 월 선택은 상세에만 영향
                            # 이 부분이 '계좌별 월별 요약' 테이블입니다.
                            st.subheader(f"--- 소유주: {selected_owner}, 연도: {selected_year_account} - 선택 계좌별 월별 {dividend_type_account} 요약 ---")
                            summary_df = get_dividend_summary_for_selection(df_div, selected_owner, selected_accounts, selected_year_account, dividend_type_account)
                            if summary_df.empty:
                                st.info("선택된 소유주, 계좌 및 연도에 배당 내역이 없습니다.")
                            else:
                                st.dataframe(
                                    summary_df.style.apply(lambda x: ['font-weight: bold' if x.name == '전체 총합' else '' for i in x], axis=1)
                                    .format(lambda x: f"{x:,.0f}" if x != 0 else ""),
                                    use_container_width=True
                                )
                                
                            # 이 부분이 '상세 내역' 테이블입니다.
                            st.subheader(f"\n--- 소유주: {selected_owner}, 계좌: {', '.join(selected_accounts)}, 연도: {selected_year_account}년 {selected_month_account}월 - {dividend_type_account} 상세 내역 ---")
                            details_df = get_monthly_details_for_selection(df_div, selected_owner, selected_accounts, selected_year_account, selected_month_account, dividend_type_account)
                            if details_df.empty:
                                st.info(f"선택된 소유주, 계좌, {selected_year_account}년 {selected_month_account}월에 배당 내역이 없습니다.")
                            else:
                                st.dataframe(
                                    details_df.style.apply(lambda x: ['font-weight: bold' if x.거래일자 == '총합' else '' for i in x], axis=1)
                                    .format({
                                    '배당금(세전)': '{:,.0f}',
                                    '제세금합': '{:,.0f}',
                                    '배당금(세후)': '{:,.0f}'
                                    }),
                                    use_container_width=True
                                )
                        else:
                            st.info("소유주, 하나 이상의 계좌, 연도, 그리고 월을 선택해주세요.")
                else:
                    st.info("상세 내역을 표시할 데이터가 없습니다.")

            with tab4:
                st.header("🔥 FIRE 현황 분석")
                # 사용자 지정 FIRE 전략 정보 반영
                st.markdown(f"**목표 월 생활비:** {4_000_000:,.0f}원")
                st.markdown("**FIRE 전략:** 배당금으로 생활, 월 400만원 생활비 목표, 배당 성장을 통한 인플레이션 극복")

                if not df_div.empty:
                    current_year = df_div['연도'].max()
                    current_year_div = df_div[df_div['연도'] == current_year]['배당금(세후)'].sum()
                    
                    # 월별 목표 계산 (사용자 정보 반영)
                    monthly_fire_goal = 4_000_000 # 사용자 정보에서 가져옴: 월 생활비 4백만원
                    annual_fire_goal = monthly_fire_goal * 12

                    st.subheader(f"{current_year}년 FIRE 목표 달성 현황")
                    st.write(f"현재까지 {current_year}년 총 세후 배당금: **{int(current_year_div):,}원**")
                    st.write(f"연간 FIRE 목표 금액: **{annual_fire_goal:,.0f}원**")

                    progress_percent = (current_year_div / annual_fire_goal) * 100 if annual_fire_goal > 0 else 0
                    st.progress(min(float(progress_percent / 100), 1.0), text=f"목표 달성률: **{progress_percent:.2f}%**")

                    if current_year_div >= annual_fire_goal:
                        st.success("🎉 축하합니다! 올해 FIRE 목표를 달성했습니다!")
                    elif current_year_div > 0:
                        st.info(f"올해 목표까지 **{int(annual_fire_goal - current_year_div):,}원**이 부족합니다.")
                    else:
                        st.info("아직 올해 배당금이 없습니다. 목표 달성을 위해 노력해봅시다!")
                    
                    st.subheader("인플레이션 극복을 위한 배당 성장률")
                    
                    # 연도별 배당금 합계 계산
                    annual_dividends = df_div.groupby('연도')['배당금(세후)'].sum().reset_index()
                    
                    if len(annual_dividends) < 2:
                        st.info("배당 성장률을 계산하기 위한 충분한 연도별 데이터(최소 2년)가 필요합니다.")
                    else:
                        # 전년 대비 배당 성장률 계산
                        annual_dividends['전년도_배당금'] = annual_dividends['배당금(세후)'].shift(1)
                        # 0으로 나누는 오류 방지
                        annual_dividends['성장률'] = annual_dividends.apply(
                            lambda row: ((row['배당금(세후)'] - row['전년도_배당금']) / row['전년도_배당금']) * 100
                            if row['전년도_배당금'] != 0 else np.nan, axis=1
                        )
                        
                        st.dataframe(annual_dividends.round(2).fillna(0).style.format({
                            '배당금(세전)': '{:,.0f}',
                            '전년도_배당금': '{:,.0f}',
                            '성장률': '{:,.2f}%'
                        }), use_container_width=True)

                        st.info("⚠️ **참고:** FIRE 전략에는 '배당 성장을 통한 인플레이션 극복'이 포함되어 있습니다. 위에 표시된 성장률이 물가 상승률보다 높은지 주기적으로 확인하는 것이 중요합니다. 한국의 물가 상승률(CPI) 데이터를 직접 비교하는 기능은 추후 추가할 수 있습니다.")
                else:
                    st.info("FIRE 현황을 분석할 데이터가 없습니다.")


        except Exception as e:
            st.error(f"❌ 파일을 처리하는 중 오류가 발생했습니다. 엑셀 파일 형식 및 내용(특히 시트 이름이 연도인지, 필요한 컬럼들이 있는지)을 확인해주세요: {e}")
            st.info("예상되는 엑셀 컬럼: '거래일자', '거래종류', '종목명', '거래금액', '외화거래금액', '제세금합', '단가', '통화코드', '소유주' 그리고 시트명은 '2024', '2025'와 같은 연도여야 합니다.")
    else:
        st.info("왼쪽 사이드바에서 엑셀 파일을 업로드하여 시작하세요.")

    st.sidebar.header("앱 정보")
    st.sidebar.info("이 앱은 개인 배당금 내역을 분석하고 FIRE(Financial Independence, Retire Early) 전략 달성 현황을 시각화합니다.")

    
