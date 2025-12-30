import streamlit as st
import pandas as pd
import numpy as np

# =========================
# CONFIG
# =========================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "master coverage"

st.set_page_config(
    page_title="Actuary Profitability Model",
    layout="wide"
)

# =========================
# SIDEBAR – ASSUMPTIONS
# =========================
st.sidebar.header("📌 Asumsi Global")

LOSS_RATIO = st.sidebar.number_input(
    "Loss Ratio (%)",
    value=50.0,
    step=1.0
) / 100

XOL_RATE = st.sidebar.number_input(
    "XOL Rate (%)",
    value=14.07,
    step=0.01
) / 100

# =========================
# LOAD MASTER EXCEL
# =========================
df_master = pd.read_excel(MASTER_FILE, sheet_name=MASTER_SHEET)
df_master.columns = df_master.columns.str.strip()

coverage_list = df_master["Coverage"].dropna().unique().tolist()

# =========================
# UI INPUT
# =========================
st.title("📊 Actuary Profitability Model")
st.subheader("📋 Input Coverage")

coverage = st.selectbox("Coverage", coverage_list)

m = df_master[df_master["Coverage"] == coverage].iloc[0]

rate = st.number_input("Rate (%)", value=0.0, format="%.5f") / 100

tsi = st.text_input("TSI IDR")
tsi = float(tsi) if tsi.strip() != "" else 0.0

top_risk_input = st.text_input("Top Risk (IDR) – default = TSI")
top_risk = tsi if top_risk_input.strip() == "" else float(top_risk_input)

askrindo_share = st.number_input("% Askrindo", value=10.0) / 100
fak_share = st.number_input("% Fakultatif", value=0.0) / 100
komisi_fak = st.number_input("% Komisi Fakultatif", value=0.0) / 100
akuisisi_rate = st.number_input("% Akuisisi", value=15.0) / 100
lol = st.number_input("% LOL", value=100.0) / 100

# =========================
# CALCULATION
# =========================
if st.button("🚀 Calculate"):

    # Exposure
    if lol > 0:
        exposure = min(top_risk, tsi) * lol
    else:
        exposure = tsi

    # Premium 100%
    prem_100 = exposure * rate

    # Askrindo
    prem_ask = prem_100 * askrindo_share
    el_ask = prem_100 * LOSS_RATIO * askrindo_share

    # Pool
    pool_rate = m["%pool"]
    pool_cap = m["Amount_Pool"]

    tsi_pool = min(
        pool_rate * prem_ask,
        pool_cap * askrindo_share
    )

    prem_pool = tsi_pool
    el_pool = prem_pool * LOSS_RATIO

    komisi_pool = prem_pool * m["Komisi_Pool"]

    # OR
    prem_or = prem_ask - prem_pool - (prem_100 * fak_share)

    # XOL
    prem_xol = XOL_RATE * prem_or

    # Expense
    expense = prem_ask * akuisisi_rate

    # Result
    result = (
        prem_ask
        - expense
        - prem_pool
        + komisi_pool
        - el_ask
        + el_pool
        - prem_xol
    )

    pct_result = result / prem_ask if prem_ask != 0 else 0

    # =========================
    # OUTPUT
    # =========================
    st.subheader("📈 Hasil Profitability")

    df_out = pd.DataFrame([{
        "Coverage": coverage,
        "Prem_Askrindo": prem_ask,
        "Prem_OR": prem_or,
        "Prem_POOL": prem_pool,
        "EL_Askrindo": el_ask,
        "EL_POOL": el_pool,
        "Prem_XOL": prem_xol,
        "Expense": expense,
        "Result": result,
        "%Result": pct_result
    }])

    for col in df_out.columns:
        if col not in ["Coverage", "%Result"]:
            df_out[col] = df_out[col].round(0).astype(int)

    df_out["%Result"] = (df_out["%Result"] * 100).round(2)

    st.dataframe(df_out, use_container_width=True)
