import streamlit as st
import pandas as pd
import numpy as np

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Actuary Profitability Model",
    layout="wide"
)

st.title("📊 Actuary Profitability Model")
st.caption("Logic fully aligned with Master Excel (Single Source of Truth)")

# =====================================================
# MASTER EXCEL (DO NOT CHANGE)
# =====================================================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "master coverage"

df_master = pd.read_excel(
    MASTER_FILE,
    sheet_name=MASTER_SHEET
)
df_master.columns = df_master.columns.str.strip()

# =====================================================
# SIDEBAR – GLOBAL ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    min_value=0.0,
    max_value=1.0,
    value=0.40,
    step=0.00001,
    format="%.5f"
)

XOL_RATE = st.sidebar.number_input(
    "Asumsi Premi XOL (% dari OR)",
    min_value=0.0,
    max_value=1.0,
    value=0.14070,
    step=0.00001,
    format="%.5f"
)

EXPENSE_RATIO = st.sidebar.number_input(
    "Asumsi Expense",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    step=0.00001,
    format="%.5f"
)

# =====================================================
# COVERAGE LIST FROM EXCEL
# =====================================================
coverage_list = df_master["Coverage"].tolist()

# =====================================================
# SESSION STATE
# =====================================================
if "rows" not in st.session_state:
    st.session_state.rows = [0]

def add_row():
    st.session_state.rows.append(len(st.session_state.rows))

def remove_row(idx):
    st.session_state.rows.pop(idx)

# =====================================================
# INPUT COVERAGE
# =====================================================
st.header("📋 Input Coverage")

inputs = []

for i in st.session_state.rows:
    st.subheader(f"Coverage #{i+1}")

    c1, c2, c3 = st.columns(3)

    with c1:
        cov = st.selectbox("Coverage", coverage_list, key=f"cov_{i}")
        rate = st.number_input(
            "Rate (%)",
            value=0.0,
            step=0.00001,
            format="%.5f",
            key=f"rate_{i}"
        )
        tsi = st.number_input(
            "TSI IDR",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.0f",
            key=f"tsi_{i}"
        )
        top_risk = st.number_input(
            "Top Risk (IDR)",
            min_value=0.0,
            value=tsi,
            step=1.0,
            format="%.0f",
            key=f"top_{i}"
        )

    with c2:
        ask = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}")
        fac = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}")
        lol = st.number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}")

    with c3:
        kom_fac = st.number_input("% Komisi Fakultatif", 0.0, 100.0, 0.0, key=f"kom_{i}")
        acq = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"acq_{i}")

    st.button("🗑️ Hapus", on_click=remove_row, args=(i,), key=f"del_{i}")

    inputs.append({
        "Coverage": cov,
        "Rate": rate / 100,
        "TSI": tsi,
        "TopRisk": top_risk,
        "LOL": lol / 100,
        "Askrindo": ask / 100,
        "Fakultatif": fac / 100,
        "KomisiFac": kom_fac / 100,
        "Akuisisi": acq / 100
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    results = []

    for r in inputs:
        m = df_master[df_master["Coverage"] == r["Coverage"]].iloc[0]

        OR_CAP = m["OR_Cap"]
        POOL_RATE = m["%pool"]
        POOL_CAP = m["Amount_Pool"]
        KOM_POOL = m["Komisi_Pool"]
        RATE_MIN = m["Rate_Min"]

        exposure_base = r["TSI"] * r["LOL"]
        TSI_Askrindo = exposure_base * r["Askrindo"]
        Exposure_OR = min(TSI_Askrindo, OR_CAP)

        TSI_POOL = min(
            POOL_RATE * Exposure_OR,
            POOL_CAP * r["Askrindo"]
        )

        TSI_FAC = exposure_base * r["Fakultatif"]
        TSI_OR = max(Exposure_OR - TSI_POOL - TSI_FAC, 0)

        Prem100 = r["Rate"] * r["TSI"] * r["LOL"]

        Prem_Askrindo = Prem100 * r["Askrindo"]
        Prem_POOL = Prem100 * (TSI_POOL / exposure_base) if exposure_base > 0 else 0
        Prem_FAC = Prem100 * r["Fakultatif"]
        Prem_OR = Prem_Askrindo - Prem_POOL - Prem_FAC

        rate_el = RATE_MIN if not pd.isna(RATE_MIN) and RATE_MIN > 0 else r["Rate"]
        EL100 = rate_el * exposure_base * LOSS_RATIO

        EL_Askrindo = EL100 * r["Askrindo"]
        EL_POOL = EL100 * (TSI_POOL / exposure_base) if exposure_base > 0 else 0
        EL_FAC = EL100 * r["Fakultatif"]

        XOL = XOL_RATE * TSI_OR
        Expense = EXPENSE_RATIO * Prem_Askrindo
        Acq = r["Akuisisi"] * Prem_Askrindo

        Result = (
            Prem_Askrindo
            - Acq
            - Prem_POOL
            - Prem_FAC
            + KOM_POOL * Prem_POOL
            + r["KomisiFac"] * Prem_FAC
            - EL_Askrindo
            + EL_POOL
            + EL_FAC
            - XOL
            - Expense
        )

        results.append({
            "Coverage": r["Coverage"],
            "Prem_Askrindo": Prem_Askrindo,
            "Prem_OR": Prem_OR,
            "Prem_POOL": Prem_POOL,
            "EL_Askrindo": EL_Askrindo,
            "EL_POOL": EL_POOL,
            "Prem_XOL": XOL,
            "Expense": Expense,
            "Result": Result,
            "%Result": Result / Prem_Askrindo if Prem_Askrindo != 0 else 0
        })

    df = pd.DataFrame(results)

    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df.style.format({
            "Prem_Askrindo": "{:,.0f}",
            "Prem_OR": "{:,.0f}",
            "Prem_POOL": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "EL_POOL": "{:,.0f}",
            "Prem_XOL": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )
