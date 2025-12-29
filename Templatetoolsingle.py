import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")

# =====================================================
# LOAD MASTER COVERAGE (BACKEND)
# =====================================================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "master coverage"

if not os.path.exists(MASTER_FILE):
    st.error(f"❌ File '{MASTER_FILE}' tidak ditemukan di repository.")
    st.stop()

try:
    df_master = pd.read_excel(MASTER_FILE, sheet_name=MASTER_SHEET)
except Exception as e:
    st.error(f"❌ Gagal membaca master coverage: {e}")
    st.stop()

df_master.columns = [c.strip() for c in df_master.columns]

# expected columns: Coverage | Rate_Min | OR_Cap
coverage_list = df_master["Coverage"].tolist()
master_map = df_master.set_index("Coverage").to_dict(orient="index")

# =====================================================
# ASSUMPTIONS (SIDEBAR) – USER INPUT %
# =====================================================
st.sidebar.header("Asumsi Profitability")

loss_ratio_pct = st.sidebar.number_input("Asumsi Loss Ratio (%)", 0.0, 100.0, 45.0, 1.0)
premi_xol_pct = st.sidebar.number_input("Asumsi Premi XOL (%)", 0.0, 100.0, 12.0, 1.0)
expense_pct = st.sidebar.number_input("Asumsi Expense (%)", 0.0, 100.0, 20.0, 1.0)

loss_ratio = loss_ratio_pct / 100
premi_xol = premi_xol_pct / 100
expense_ratio = expense_pct / 100

# =====================================================
# METADATA POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

insured = st.text_input("Nama Tertanggung")
start_date = st.date_input("Periode Mulai")
end_date = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE – SESSION SAFE
# =====================================================
st.subheader("📋 Input Coverage")

default_row = {
    "Coverage": coverage_list[0],
    "Rate (%)": 10.0,            # user input 10 = 10%
    "TSI_IDR": 0.0,
    "Limit_IDR": 0.0,
    "TopRisk_IDR": 0.0,
    "% Askrindo Share": 100.0,
    "% Fakultatif Share": 0.0,
    "% Komisi Fakultatif": 0.0,
    "% LOL Premi": 100.0,
    "% Akuisisi": 15.0
}

if "df_input" not in st.session_state:
    st.session_state.df_input = pd.DataFrame([default_row])

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Coverage": st.column_config.SelectboxColumn(
            options=coverage_list
        ),
        "Rate (%)": st.column_config.NumberColumn(format="%.2f"),
        "% Askrindo Share": st.column_config.NumberColumn(format="%.2f"),
        "% Fakultatif Share": st.column_config.NumberColumn(format="%.2f"),
        "% Komisi Fakultatif": st.column_config.NumberColumn(format="%.2f"),
        "% LOL Premi": st.column_config.NumberColumn(format="%.2f"),
        "% Akuisisi": st.column_config.NumberColumn(format="%.2f"),
        "TSI_IDR": st.column_config.NumberColumn(format="%,.0f"),
        "Limit_IDR": st.column_config.NumberColumn(format="%,.0f"),
        "TopRisk_IDR": st.column_config.NumberColumn(format="%,.0f"),
    }
)

st.session_state.df_input = edited_df

def add_row():
    st.session_state.df_input = pd.concat(
        [st.session_state.df_input, pd.DataFrame([default_row])],
        ignore_index=True
    )

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CORE ENGINE (IDENTIK BULK)
# =====================================================
def run_profitability(row):

    cov = row["Coverage"]
    rate_min = master_map[cov]["Rate_Min"]
    or_cap = master_map[cov]["OR_Cap"]

    rate = row["Rate (%)"] / 100
    ask_share = row["% Askrindo Share"] / 100
    fac_share = row["% Fakultatif Share"] / 100
    komisi_fac = row["% Komisi Fakultatif"] / 100
    lol_pct = row["% LOL Premi"] / 100
    acq_pct = row["% Akuisisi"] / 100

    ExposureBasis = max(row["Limit_IDR"], row["TopRisk_IDR"])
    Exposure_OR = min(ExposureBasis, or_cap)
    S_Askrindo = ask_share * Exposure_OR

    # ===== POOL =====
    if cov.upper().startswith("FIRE"):
        Pool_amt = min(0.025 * S_Askrindo, 500_000_000 * ask_share)
        komisi_pool = 0.35
    elif cov.upper().startswith("EQVET"):
        rate_pool = 0.10 if "DKI" in cov.upper() or "JABAR" in cov.upper() or "BANTEN" in cov.upper() else 0.25
        Pool_amt = min(rate_pool * S_Askrindo, 10_000_000_000 * ask_share)
        komisi_pool = 0.30
    else:
        Pool_amt = 0
        komisi_pool = 0

    Fac_amt = fac_share * Exposure_OR
    OR_amt = max(S_Askrindo - Pool_amt - Fac_amt, 0)
    Shortfall_amt = max(Exposure_OR - (Pool_amt + Fac_amt + OR_amt), 0)
    pct_pool = Pool_amt / Exposure_OR if Exposure_OR > 0 else 0

    # ===== PREMIUM =====
    Prem100 = rate * lol_pct * row["TSI_IDR"]
    Prem_Askrindo = Prem100 * ask_share + rate * lol_pct * Shortfall_amt
    Prem_POOL = Prem100 * pct_pool
    Prem_Fac = Prem100 * fac_share

    Acq_amt = acq_pct * Prem_Askrindo
    Komisi_POOL = komisi_pool * Prem_POOL
    Komisi_Fak = komisi_fac * Prem_Fac

    # ===== EXPECTED LOSS =====
    if pd.isna(rate_min):
        EL_100 = loss_ratio * Prem100
    else:
        EL_100 = rate_min * ExposureBasis * loss_ratio

    EL_Askrindo = EL_100 * ask_share + EL_100 * (Shortfall_amt / ExposureBasis if ExposureBasis > 0 else 0)
    EL_POOL = EL_100 * pct_pool
    EL_Fac = EL_100 * fac_share

    XL_cost = premi_xol * OR_amt
    Expense = expense_ratio * Prem_Askrindo

    Result = (
        Prem_Askrindo
        - Prem_POOL - Prem_Fac
        - Acq_amt
        + Komisi_POOL + Komisi_Fak
        - EL_Askrindo
        + EL_POOL + EL_Fac
        - XL_cost - Expense
    )

    return {
        "Exposure_OR": Exposure_OR,
        "Prem_Askrindo": Prem_Askrindo,
        "EL_Askrindo": EL_Askrindo,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo != 0 else 0
    }

# =====================================================
# RUN CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    output = []
    warnings = []

    for _, r in st.session_state.df_input.iterrows():
        res = run_profitability(r)
        output.append({**r.to_dict(), **res})

        if not pd.isna(master_map[r["Coverage"]]["Rate_Min"]) and r["Rate (%)"]/100 < master_map[r["Coverage"]]["Rate_Min"]:
            warnings.append(f"⚠️ Rate di bawah minimum untuk {r['Coverage']}")

    df_result = pd.DataFrame(output)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df_result.style.format({
            "TSI_IDR": "{:,.0f}",
            "Limit_IDR": "{:,.0f}",
            "TopRisk_IDR": "{:,.0f}",
            "Exposure_OR": "{:,.0f}",
            "Prem_Askrindo": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )

    for w in warnings:
        st.warning(w)
