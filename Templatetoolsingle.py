import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="📊 Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.markdown("## 📊 **Profitability Checking – Akseptasi Manual**")
st.caption("Versi Excel-driven | Logic match Bulk Profitability")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
@st.cache_data
def load_master():
    df = pd.read_excel("Master File.xlsx", sheet_name="master coverage")
    df.columns = df.columns.str.strip()
    return df

df_master = load_master()

MASTER = {
    r["Coverage"]: {
        "rate_min": r["Rate_Min"] if not pd.isna(r["Rate_Min"]) else None,
        "or_cap": r["OR_Cap"],
        "pool": r["%pool"],
        "pool_cap": r["Amount_Pool"] if not pd.isna(r["Amount_Pool"]) else 0,
        "kom_pool": r["Komisi_Pool"]
    }
    for _, r in df_master.iterrows()
}

COVERAGE_LIST = df_master["Coverage"].tolist()

# =====================================================
# POLICY INFO
# =====================================================
st.markdown("### 📄 Informasi Polis")
c1, c2, c3 = st.columns(3)

with c1:
    insured = st.text_input("Nama Tertanggung", "")
with c2:
    start_date = st.date_input("Periode Mulai")
with c3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# ASSUMPTIONS
# =====================================================
st.sidebar.markdown("## ⚙️ Asumsi Profitability")

loss_ratio    = st.sidebar.number_input("Loss Ratio", 0.0, 1.0, 0.40, 0.01)
premi_xol_pct = st.sidebar.number_input("Premi XOL (%)", 0.0, 100.0, 12.0, 0.01)
expense_pct   = st.sidebar.number_input("Expense (%)", 0.0, 100.0, 15.0, 0.01)

premi_xol  = premi_xol_pct / 100
expense_rt = expense_pct / 100

# =====================================================
# INIT INPUT TABLE (SAFE)
# =====================================================
def empty_row():
    return {
        "Delete": False,
        "Coverage": COVERAGE_LIST[0],
        "Rate (%)": 0.0,
        "TSI_IDR": 0.0,
        "% Askrindo": 10.0,
        "% Fakultatif": 0.0,
        "% Komisi Fakultatif": 0.0,
        "% LOL": 100.0,
        "% Akuisisi": 15.0,
    }

if "df_input" not in st.session_state:
    st.session_state.df_input = pd.DataFrame([empty_row()])

# =====================================================
# INPUT TABLE
# =====================================================
st.markdown("### 🧾 Input Coverage")

edited = st.data_editor(
    st.session_state.df_input,
    column_config={
        "Delete": st.column_config.CheckboxColumn("🗑"),
        "Coverage": st.column_config.SelectboxColumn("Coverage", options=COVERAGE_LIST),
        "Rate (%)": st.column_config.NumberColumn("Rate (%)", format="%.5f", step=0.00001),
        "TSI_IDR": st.column_config.NumberColumn("TSI IDR", format="%,.0f"),
    },
    use_container_width=True,
    num_rows="fixed"
)

# ==========================
# DELETE ROW (SAFE)
# ==========================
edited = edited[~edited["Delete"]].copy()

# Kalau habis → seed ulang 1 row kosong
if edited.empty:
    edited = pd.DataFrame([empty_row()])

edited["Delete"] = False
st.session_state.df_input = edited

# ==========================
# ADD ROW
# ==========================
if st.button("➕ Tambah Coverage"):
    st.session_state.df_input = pd.concat(
        [st.session_state.df_input, pd.DataFrame([empty_row()])],
        ignore_index=True
    )

# =====================================================
# CORE ENGINE
# =====================================================
def run_profitability(df):
    rows = []

    for _, r in df.iterrows():
        m = MASTER[r["Coverage"]]

        rate = r["Rate (%)"] / 100
        tsi  = r["TSI_IDR"]
        ask  = r["% Askrindo"] / 100
        fac  = r["% Fakultatif"] / 100

        exposure = min(tsi, m["or_cap"])
        S_ask = ask * exposure

        pool_amt = min(m["pool"] * S_ask, m["pool_cap"] * ask) if m["pool"] > 0 else 0
        fac_amt  = fac * exposure
        OR_amt   = max(S_ask - pool_amt - fac_amt, 0)

        prem100  = rate * tsi
        prem_ask = prem100 * ask
        prem_or  = prem100 * (OR_amt / exposure) if exposure > 0 else 0

        if m["rate_min"] is not None:
            EL_100 = m["rate_min"] * tsi * loss_ratio
        else:
            EL_100 = loss_ratio * prem100

        EL_ask = EL_100 * ask

        XL_cost = premi_xol * prem_or
        expense = expense_rt * prem_ask
        acq     = (r["% Akuisisi"] / 100) * prem_ask

        result = prem_ask - acq - EL_ask - XL_cost - expense

        rows.append([
            r["Coverage"], exposure, prem_ask, prem_or,
            EL_ask, XL_cost, expense, result
        ])

    out = pd.DataFrame(rows, columns=[
        "Coverage","Exposure_OR","Prem_Askrindo","Prem_OR",
        "EL_Askrindo","XOL","Expense","Result"
    ])

    total = out.iloc[:,1:].sum()
    total["Coverage"] = "TOTAL"
    out = pd.concat([out, total.to_frame().T], ignore_index=True)

    out["%Result"] = out["Result"] / out["Prem_Askrindo"]
    return out

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    res = run_profitability(st.session_state.df_input)

    st.markdown("### 📈 Hasil Profitability")
    st.dataframe(
        res.style
        .format("{:,.0f}", subset=res.columns[1:-1])
        .format("{:.2%}", subset=["%Result"]),
        use_container_width=True
    )
