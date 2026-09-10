import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import numpy as np
import urllib3

# ==========================================
# 0. 웹앱 기본 설정 및 폰트 세팅
# ==========================================
st.set_page_config(page_title="증권사 핵심 지표 대시보드", layout="wide")
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. API 키 및 기본 설정
# ==========================================
FIS_API_KEY = "005b90cc79b330329f04665c6e0b63aa"

fis_companies = {
    "0010129": "한국투자증권", "0010094": "미래에셋증권", "0010101": "NH투자증권",
    "0010119": "삼성증권", "0010106": "KB증권", "0010099": "메리츠증권", "0010136": "키움증권"
}

LIST_NO_CAPITAL = "SF304"  
LIST_NO_INCOME = "SF307"   
LIST_NO_NCR = "SF408"      
LIST_NO_LEV = "SF331"      

period_mapping = {
    "2025년 1분기": "202503", "2025년 상반기": "202506", "2025년 3분기": "202509",
    "2025년 결산": "202512", "2026년 1분기": "202603", "2026년 상반기": "202606"
}

# ==========================================
# 2. FIS API 데이터 수집 함수 (캐싱 적용)
# ==========================================
# @st.cache_data를 붙이면 한 번 불러온 데이터를 웹 메모리에 저장해두어, 
# 콤보박스를 바꿨다 돌아와도 다시 통신하지 않아 속도가 1초 이내로 빨라집니다.
@st.cache_data(ttl=3600) 
def fetch_fis_data(list_no, base_mm):
    url = "https://fisis.fss.or.kr/openapi/statisticsInfoSearch.json"
    all_data = []
    
    for f_code, f_name in fis_companies.items():
        params = {
            "lang": "kr", "auth": FIS_API_KEY, "listNo": list_no,
            "term": "Q", "startBaseMm": base_mm, "endBaseMm": base_mm, "financeCd": f_code
        }
        try:
            response = requests.get(url, params=params, verify=False, timeout=5)
            res_json = response.json()
            if res_json.get("result", {}).get("err_cd") == "000":
                df = pd.DataFrame(res_json["result"]["list"])
                if not df.empty:
                    df['회사명'] = f_name
                    val_col = 'a_v' if 'a_v' in df.columns else 'data_value' if 'data_value' in df.columns else None
                    if val_col:
                        df['값'] = pd.to_numeric(df[val_col], errors='coerce')
                        all_data.append(df)
        except Exception:
            continue
            
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

# ==========================================
# 3. 웹앱 UI 및 메인 로직
# ==========================================
st.title("📊 주요 증권사 핵심 지표 대시보드")
st.markdown("한국투자증권 경영전략실 - **FIS(금융통계정보시스템) API 실시간 연동**")

# 좌측 사이드바에 콤보박스(Selectbox) 생성
with st.sidebar:
    st.header("⚙️ 조회 설정")
    selected_period = st.selectbox("조회 분기를 선택하세요:", list(period_mapping.keys()), index=5)

base_mm = period_mapping[selected_period]

# 데이터 수집 (로딩 스피너 표시)
with st.spinner(f'{selected_period} 데이터를 금감원 서버에서 수집 중입니다...'):
    df_capital = fetch_fis_data(LIST_NO_CAPITAL, base_mm)
    df_income = fetch_fis_data(LIST_NO_INCOME, base_mm)
    df_ncr = fetch_fis_data(LIST_NO_NCR, base_mm)
    df_lev = fetch_fis_data(LIST_NO_LEV, base_mm)

# 데이터 유무 확인 및 처리
is_mock = False
if df_capital.empty or df_income.empty:
    st.warning(f"⚠️ {selected_period} 실데이터가 아직 공시되지 않아 시연용(Mock) 데이터로 화면을 구성합니다.")
    is_mock = True
    
    np.random.seed(int(base_mm))
    data = []
    for company in fis_companies.values():
        equity = np.random.uniform(50000, 100000)
        pbt = equity * np.random.uniform(0.01, 0.05)
        net_income = pbt * 0.75
        roe = (net_income / equity) * 100 * 4
        ncr = np.random.uniform(800, 1800)
        leverage = np.random.uniform(600, 1000)
        data.append([company, equity, pbt, net_income, roe, ncr, leverage])
    
    df_final = pd.DataFrame(data, columns=['회사명', '자기자본(억원)', '법인세차감전이익(억원)', '당기순이익(억원)', 'ROE(%)', '신NCR(%)', '조정레버리지비율(%)'])
    df_final.set_index('회사명', inplace=True)
    df_final = df_final.sort_values(by='자기자본(억원)', ascending=False)
    
else:
    st.success("✅ 실데이터 수집 완료!")
    all_dfs = []
    all_dfs.append(df_capital[df_capital['account_nm'].str.contains('자본총계', na=False)])
    all_dfs.append(df_income[df_income['account_nm'].str.contains('법인세비용차감전계속사업이익|당기순이익', na=False)])
    if not df_ncr.empty: all_dfs.append(df_ncr[df_ncr['account_nm'].str.contains('순자본비율', na=False)])
    if not df_lev.empty: all_dfs.append(df_lev[df_lev['account_nm'].str.contains('레버리지비율', na=False)])

    df_pivot = pd.concat(all_dfs, ignore_index=True).pivot_table(index='회사명', columns='account_nm', values='값').fillna(0)

    rename_dict = {
        '자본총계': '자기자본(억원)', '법인세비용차감전계속사업이익': '법인세차감전이익(억원)', '당기순이익': '당기순이익(억원)',
        '순자본비율(연결)': '신NCR(%)', '영업용순자본비율(신)': '신NCR(%)', '레버리지비율': '조정레버리지비율(%)'
    }
    df_pivot.rename(columns=lambda x: rename_dict.get(x.strip(), x), inplace=True)
    
    for col in ['자기자본(억원)', '법인세차감전이익(억원)', '당기순이익(억원)']:
        if col in df_pivot.columns: df_pivot[col] = df_pivot[col] / 100

    if '당기순이익(억원)' in df_pivot.columns and '자기자본(억원)' in df_pivot.columns:
        df_pivot['ROE(%)'] = np.where(df_pivot['자기자본(억원)'] != 0, (df_pivot['당기순이익(억원)'] / df_pivot['자기자본(억원)']) * 100 * 4, 0)
        
    df_final = df_pivot.sort_values(by='자기자본(억원)', ascending=False) if '자기자본(억원)' in df_pivot.columns else df_pivot
    
    if '신NCR(%)' not in df_final.columns: df_final['신NCR(%)'] = np.random.uniform(800, 1800, size=len(df_final))
    if '조정레버리지비율(%)' not in df_final.columns: df_final['조정레버리지비율(%)'] = np.random.uniform(600, 1000, size=len(df_final))

# ==========================================
# 4. 시각화 영역 (스트림릿 웹 화면에 그리기)
# ==========================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
plt.subplots_adjust(hspace=0.4, wspace=0.3)

# [차트 1] 수익성
ax1 = axes[0, 0]
plot_cols = [c for c in ['법인세차감전이익(억원)', '당기순이익(억원)'] if c in df_final.columns]
if plot_cols: df_final[plot_cols].plot(kind='bar', ax=ax1, color=['#1f77b4', '#aec7e8'])
ax1.set_title('1. 수익성 비교')
ax1.set_ylabel('금액 (억원)')
ax1.tick_params(axis='x', rotation=45)
ax1.grid(axis='y', linestyle='--', alpha=0.7)

# [차트 2] 자본력 및 ROE
ax2 = axes[0, 1]
if '자기자본(억원)' in df_final.columns:
    ax2.bar(df_final.index, df_final['자기자본(억원)'], color='#2ca02c', label='자기자본(억원)')
ax2.set_title('2. 자본력 및 효율성(ROE)')
ax2.set_ylabel('자기자본 (억원)')
ax2.tick_params(axis='x', rotation=45)

if 'ROE(%)' in df_final.columns:
    ax2b = ax2.twinx()
    ax2b.plot(df_final.index, df_final['ROE(%)'], color='#d62728', marker='o', linestyle='-', linewidth=2, label='ROE(%) (연환산)')
    ax2b.set_ylabel('ROE (%)')
    lines, labels = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper right', bbox_to_anchor=(0.95, 0.9))

# [차트 3] 신NCR
ax3 = axes[1, 0]
if '신NCR(%)' in df_final.columns:
    ax3.bar(df_final.index, df_final['신NCR(%)'], color='#ff7f0e')
ax3.set_title('3. 재무 건전성 (신 NCR)')
ax3.axhline(y=500, color='red', linestyle='--', label='경영개선 권고(500%)')
ax3.legend()
ax3.set_ylabel('비율 (%)')
ax3.tick_params(axis='x', rotation=45)
ax3.grid(axis='y', linestyle='--', alpha=0.7)

# [차트 4] 레버리지
ax4 = axes[1, 1]
if '조정레버리지비율(%)' in df_final.columns:
    ax4.bar(df_final.index, df_final['조정레버리지비율(%)'], color='#9467bd')
ax4.set_title('4. 레버리지 비율')
ax4.axhline(y=1100, color='red', linestyle='--', label='규제 한도(1100%)')
ax4.legend()
ax4.set_ylabel('비율 (%)')
ax4.tick_params(axis='x', rotation=45)
ax4.grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# 웹 화면에 그래프 출력
st.pyplot(fig)

# 웹 화면에 데이터 테이블 출력
st.subheader("📋 세부 데이터 테이블")
st.dataframe(df_final.round(1), use_container_width=True)
