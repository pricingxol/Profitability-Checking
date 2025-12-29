import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")
st.caption("Versi Excel-driven | Logic match Bulk Profitability")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
BASE_DIR = Path(__file__).resolve().parent
MASTER_FILE = BASE_DIR / "Master File.xlsx"

@st.cache_data
def load_master():
    df = pd.read_excel(MASTER_FILE, sheet_name="MASTER")
    df.columns = df.columns.str.strip()
    return df

df_master = load_master()

# =====================================================
# SIDEBAR – ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE   = st.sidebar.number_input("Premi XOL (%)", 0.0, 1.0, 0.1407, 0.0001)
EXP_RATIO  = st.sidebar.number_input("Expense (%)", 0.0, 1.0, 0.15, 0.01)

# =====================================================
# INFORMASI POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

col1, col2, col3 = st.columns(3)
with col1:
    insured_name = st.text_input("Nama Tertanggung", "")
with col2:
    start_date = st.date_input("Periode Mulai")
with col3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("🧾 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = [{}]

def add_row():
    st.session_state.rows.append({})

def delete_row(i):
    st.session_state.rows.pop(i)

coverage_list = df_master["Coverage"].tolist()

for i, row in enumerate(st.session_state.rows):
    cols = st.columns([2,1,2,1,1,1,1,1,0.4])

    with cols[0]:
        row["Coverage"] = st.selectbox(
            "Coverage", coverage_list,
            key=f"cov_{i}"
        )

    with cols[1]:
        row["Rate"] = st.number_input(
            "Rate (%)", min_value=0.0,
            format="%.5f", key=f"rate_{i}"
        )

    with cols[2]:
        row["TSI"] = st.number_input(
            "TSI IDR", min_value=0.0,
            format="%.0f", key=f"tsi_{i}"
        )

    with cols[3]:
        row["Ask"] = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}") / 100

    with cols[4]:
        row["Fac"] = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}") / 100

    with cols[5]:
        row["KomFac"] = st.number_input("% Komisi Fak", 0.0, 100.0, 0.0, key=f"kom_{i}") / 100

    with cols[6]:
        row["LOL"] = st.number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}") / 100

    with cols[7]:
        row["Aku"] = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"aku_{i}") / 100

    with cols[8]:
        st.button("🗑", on_click=delete_row, args=(i,), key=f"del_{i}")

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CORE CALCULATION
# =====================================================
def calc_profit(row):
    m = df_master[df_master["Coverage"] == row["Coverage"]].iloc[0]

    RATE_MIN = m["Rate_Min"]
    OR_CAP   = m["OR_Cap"]
    POOL_RT  = m["%pool"]
    POOL_CAP = m["Amount_Pool"]
    KOM_POOL = m["Komisi_Pool"]

    rate = max(row["Rate"]/100, RATE_MIN if not pd.isna(RATE_MIN) else 0)

    TSI100 = row["TSI"] * row["LOL"]

    # ===== TSI SPLIT (FINAL LOGIC) =====
    TSI_ASK = row["Ask"] * TSI100
    TSI_POOL = min(POOL_RT * TSI_ASK, POOL_CAP * row["Ask"])
    TSI_FAC = row["Fac"] * TSI100
    TSI_OR = max(TSI_ASK - TSI_POOL - TSI_FAC, 0)

    # ===== PREMIUM =====
    Prem100 = rate * TSI100
    Prem_ASK = Prem100 * row["Ask"]
    Prem_POOL = Prem100 * (TSI_POOL / TSI100 if TSI100 > 0 else 0)
    Prem_FAC = Prem100 * row["Fac"]
    Prem_OR = Prem100 * (TSI_OR / TSI100 if TSI100 > 0 else 0)

    # ===== COMMISSION =====
    Akuisisi = row["Aku"] * Prem_ASK
    Kom_POOL = KOM_POOL * Prem_POOL
    Kom_FAC = row["KomFac"] * Prem_FAC

    # ===== EXPECTED LOSS =====
    EL100 = rate * LOSS_RATIO * TSI100
    EL_ASK = EL100 * row["Ask"]
    EL_POOL = EL100 * (TSI_POOL / TSI100 if TSI100 > 0 else 0)
    EL_FAC = EL100 * row["Fac"]

    # ===== COST =====
    XOL = XOL_RATE * Prem_OR
    Expense = EXP_RATIO * Prem_ASK

    # ===== RESULT (LOCKED) =====
    Result = (
        Prem_ASK
        - Akuisisi
        - Prem_POOL
        - Prem_FAC
        + Kom_POOL
        + Kom_FAC
        - EL_ASK
        + EL_POOL
        + EL_FAC
        - XOL
        - Expense
    )

    return {
        "Coverage": row["Coverage"],
        "Prem_Askrindo": Prem_ASK,
        "Prem_OR": Prem_OR,
        "Prem_POOL": Prem_POOL,
        "EL_Askrindo": EL_ASK,
        "EL_POOL": EL_POOL,
        "Prem_XOL": XOL,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_ASK if Prem_ASK != 0 else 0
    }

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    results = [calc_profit(r) for r in st.session_state.rows if r]

    df = pd.DataFrame(results)
    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df.style.format({
            c: "{:,.0f}" for c in df.columns if c not in ["Coverage","%Result"]
        } | {"%Result": "{:.2%}"}
    )
