import streamlit as st
import pandas as pd
import numpy as np

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")

# ===============================
# LOAD MASTER COVERAGE
# ===============================
MASTER_FILE = "Master File.xlsx"
df_master = pd.read_excel(MASTER_FILE)

df_master["Coverage"] = df_master["Coverage"].astype(str)

master_map = df_master.set_index("Coverage").to_dict("index")

coverage_list = list(master_map.keys())

# ===============================
# SIDEBAR ASSUMPTIONS
# ===============================
st.sidebar.header("Asumsi Profitability")

loss_ratio = st.sidebar.number_input(
    "Asumsi Loss Ratio", value=0.45, min_value=0.0, max_value=1.0, step=0.01
)

premi_xol_pct = st.sidebar.number_input(
    "Asumsi Premi XOL (%)", value=12.0, min_value=0.0, max_value=100.0, step=0.1
) / 100

expense_pct = st.sidebar.number_input(
    "Asumsi Expense (%)", value=20.0, min_value=0.0, max_value=100.0, step=0.1
) / 100

# ===============================
# POLICY INFO
# ===============================
st.subheader("📄 Informasi Polis")

insured_name = st.text_input("Nama Tertanggung")
start_date = st.date_input("Periode Mulai")
end_date = st.date_input("Periode Akhir")

# ===============================
# INPUT COVERAGE TABLE
# ===============================
st.subheader("📋 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = 1

def add_row():
    st.session_state.rows += 1

input_df = pd.DataFrame({
    "Coverage": [coverage_list[0]] * st.session_state.rows,
    "Rate (%)": [0.0] * st.session_state.rows,
    "TSI_IDR": [0.0] * st.session_state.rows,
    "Limit_IDR": [0.0] * st.session_state.rows,
    "TopRisk_IDR": [0.0] * st.session_state.rows,
    "% Askrindo Share": [10.0] * st.session_state.rows,
    "% Fakultatif Share": [0.0] * st.session_state.rows,
    "% Komisi Fakultatif": [0.0] * st.session_state.rows,
    "% LOL Premi": [100.0] * st.session_state.rows,
    "% Akuisisi": [15.0] * st.session_state.rows,
})

edited_df = st.data_editor(
    input_df,
    num_rows="fixed",
    use_container_width=True,
    column_config={
        "Coverage": st.column_config.SelectboxColumn(
            "Coverage", options=coverage_list
        )
    }
)

st.button("➕ Tambah Coverage", on_click=add_row)

# ===============================
# CORE ENGINE
# ===============================
def run_profitability(row):
    cov = row["Coverage"]
    m = master_map[cov]

    rate = row["Rate (%)"] / 100
    ask = row["% Askrindo Share"] / 100
    fac = row["% Fakultatif Share"] / 100
    lol = row["% LOL Premi"] / 100
    acq = row["% Akuisisi"] / 100
    kom_fac = row["% Komisi Fakultatif"] / 100

    tsi = row["TSI_IDR"]
    limit_ = row["Limit_IDR"]
    top = row["TopRisk_IDR"]

    exposure_basis = max(tsi, limit_, top)
    exposure_or = min(exposure_basis, m["OR_Cap"])

    # ===== SHARE (SI) =====
    SI_Askrindo = ask * exposure_or

    pool_pct = m["%pool"] / 100 if not pd.isna(m["%pool"]) else 0
    pool_cap = m["Amount_Pool"] if not pd.isna(m["Amount_Pool"]) else 0
    kom_pool = m["Komisi_Pool"] / 100 if not pd.isna(m["Komisi_Pool"]) else 0

    SI_Pool = min(pool_pct * SI_Askrindo, pool_cap * ask)
    SI_Fac = fac * exposure_or
    SI_OR = max(SI_Askrindo - SI_Pool - SI_Fac, 0)

    # ===== PREMIUM =====
    Prem100 = rate * lol * exposure_or
    Prem_Askrindo = ask * Prem100
    Prem_OR = (SI_OR / exposure_or) * Prem100 if exposure_or > 0 else 0
    Prem_POOL = (SI_Pool / exposure_or) * Prem100 if exposure_or > 0 else 0
    Prem_Fac = fac * Prem100

    # ===== COMMISSION =====
    Akuisisi = acq * Prem_Askrindo
    Komisi_POOL = kom_pool * Prem_POOL
    Komisi_Fac = kom_fac * Prem_Fac

    # ===== EXPECTED LOSS =====
    rate_min = m["Rate_Min"]

    if pd.isna(rate_min):
        EL100 = loss_ratio * Prem100
    else:
        EL100 = rate_min * loss_ratio * exposure_or

    EL_Askrindo = (SI_Askrindo / exposure_or) * EL100 if exposure_or > 0 else 0
    EL_Pool = (SI_Pool / exposure_or) * EL100 if exposure_or > 0 else 0
    EL_Fac = (SI_Fac / exposure_or) * EL100 if exposure_or > 0 else 0

    # ===== COST =====
    XOL_cost = premi_xol_pct * Prem_OR
    Expense = expense_pct * Prem_Askrindo

    # ===== RESULT =====
    Result = (
        Prem_Askrindo
        - Prem_POOL
        - Prem_Fac
        - Akuisisi
        + Komisi_POOL
        + Komisi_Fac
        - EL_Askrindo
        + EL_Pool
        + EL_Fac
        - XOL_cost
        - Expense
    )

    return {
        "Exposure_OR": exposure_or,
        "Prem_Askrindo": Prem_Askrindo,
        "Prem_OR": Prem_OR,
        "EL_Askrindo": EL_Askrindo,
        "XOL_cost": XOL_cost,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
    }

# ===============================
# CALCULATE
# ===============================
if st.button("🚀 Calculate"):
    results = edited_df.apply(run_profitability, axis=1, result_type="expand")

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        results.style.format({
            "Exposure_OR": "{:,.0f}",
            "Prem_Askrindo": "{:,.0f}",
            "Prem_OR": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "XOL_cost": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}",
        }),
        use_container_width=True
    )
