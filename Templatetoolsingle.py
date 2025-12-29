import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
from datetime import datetime

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")

# =====================================================
# LOAD MASTER COVERAGE
# =====================================================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "master coverage"

if not os.path.exists(MASTER_FILE):
    st.error(f"❌ File '{MASTER_FILE}' tidak ditemukan.")
    st.stop()

df_master = pd.read_excel(MASTER_FILE, sheet_name=MASTER_SHEET)
df_master.columns = [c.strip() for c in df_master.columns]

coverage_list = df_master["Coverage"].tolist()
master_map = df_master.set_index("Coverage").to_dict(orient="index")

# =====================================================
# ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

loss_ratio = st.sidebar.number_input("Loss Ratio (%)", 0.0, 100.0, 45.0, 1.0) / 100
premi_xol = st.sidebar.number_input("Premi XOL (%)", 0.0, 100.0, 12.0, 1.0) / 100
expense_ratio = st.sidebar.number_input("Expense (%)", 0.0, 100.0, 20.0, 1.0) / 100

# =====================================================
# METADATA POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

insured = st.text_input("Nama Tertanggung")
start_date = st.date_input("Periode Mulai")
end_date = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("📋 Input Coverage")

default_row = {
    "Coverage": coverage_list[0],
    "Rate (%)": 0.0,               # DEFAULT 0
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
        "Coverage": st.column_config.SelectboxColumn(options=coverage_list),

        # RATE → 5 desimal
        "Rate (%)": st.column_config.NumberColumn(format=",.5f"),

        # AMOUNT
        "TSI_IDR": st.column_config.NumberColumn(format=",.0f"),
        "Limit_IDR": st.column_config.NumberColumn(format=",.0f"),
        "TopRisk_IDR": st.column_config.NumberColumn(format=",.0f"),

        # PERCENT (2 desimal)
        "% Askrindo Share": st.column_config.NumberColumn(format=",.2f"),
        "% Fakultatif Share": st.column_config.NumberColumn(format=",.2f"),
        "% Komisi Fakultatif": st.column_config.NumberColumn(format=",.2f"),
        "% LOL Premi": st.column_config.NumberColumn(format=",.2f"),
        "% Akuisisi": st.column_config.NumberColumn(format=",.2f"),
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
# CORE ENGINE (TIDAK DIUBAH)
# =====================================================
def run_profitability(row):

    cov = row["Coverage"]
    rate_min = master_map[cov]["Rate_Min"]
    or_cap = master_map[cov]["OR_Cap"]

    rate = row["Rate (%)"] / 100
    ask = row["% Askrindo Share"] / 100
    fac = row["% Fakultatif Share"] / 100
    kom_fak = row["% Komisi Fakultatif"] / 100
    lol = row["% LOL Premi"] / 100
    acq = row["% Akuisisi"] / 100

    ExposureBasis = max(row["Limit_IDR"], row["TopRisk_IDR"])
    Exposure_OR = min(ExposureBasis, or_cap)
    S_Askrindo = ask * Exposure_OR

    # POOL
    if cov.upper().startswith("FIRE"):
        Pool = min(0.025 * S_Askrindo, 500_000_000 * ask)
        kom_pool = 0.35
    elif cov.upper().startswith("EQVET"):
        pool_rate = 0.10 if any(x in cov.upper() for x in ["DKI", "JABAR", "BANTEN"]) else 0.25
        Pool = min(pool_rate * S_Askrindo, 10_000_000_000 * ask)
        kom_pool = 0.30
    else:
        Pool = 0
        kom_pool = 0

    Fac = fac * Exposure_OR
    OR = max(S_Askrindo - Pool - Fac, 0)
    Shortfall = max(Exposure_OR - (Pool + Fac + OR), 0)
    pct_pool = Pool / Exposure_OR if Exposure_OR else 0

    Prem100 = rate * lol * row["TSI_IDR"]
    Prem_Askrindo = Prem100 * ask + rate * lol * Shortfall

    Acq = acq * Prem_Askrindo
    KomPool = kom_pool * Prem100 * pct_pool
    KomFak = kom_fak * Prem100 * fac

    # EL
    EL100 = loss_ratio * Prem100 if pd.isna(rate_min) else rate_min * ExposureBasis * loss_ratio
    EL_Askrindo = EL100 * ask + EL100 * (Shortfall / ExposureBasis if ExposureBasis else 0)

    XL = premi_xol * OR
    Exp = expense_ratio * Prem_Askrindo

    Result = (
        Prem_Askrindo
        - Prem100 * pct_pool - Prem100 * fac
        - Acq + KomPool + KomFak
        - EL_Askrindo + EL100 * pct_pool + EL100 * fac
        - XL - Exp
    )

    return {
        "Exposure_OR": Exposure_OR,
        "Prem_Askrindo": Prem_Askrindo,
        "EL_Askrindo": EL_Askrindo,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
    }

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    out = []
    for _, r in st.session_state.df_input.iterrows():
        out.append({**r.to_dict(), **run_profitability(r)})

    df_res = pd.DataFrame(out)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df_res.style.format({
            "Exposure_OR": "{:,.0f}",
            "Prem_Askrindo": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )
