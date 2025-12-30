import streamlit as st
import pandas as pd
import numpy as np

# ===============================
# CONFIG
# ===============================
st.set_page_config(
    page_title="Actuary Profitability Model",
    layout="wide"
)

st.title("📊 Actuary Profitability Model")
st.caption("Excel-driven | Logic aligned with Bulk Profitability Model")

# ===============================
# LOAD MASTER EXCEL
# ===============================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "MASTER"

df_master = pd.read_excel(MASTER_FILE, sheet_name=MASTER_SHEET)
df_master.columns = df_master.columns.str.strip()

MASTER = df_master.set_index("Coverage").to_dict(orient="index")
COVERAGE_LIST = list(MASTER.keys())

# ===============================
# ASSUMPTIONS
# ===============================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input(
    "Loss Ratio", 0.0, 1.0, 0.40, step=0.00001, format="%.5f"
)

XOL_RATE = st.sidebar.number_input(
    "Premi XOL (%)", 0.0, 1.0, 0.1407, step=0.00001, format="%.5f"
)

EXPENSE_RATE = st.sidebar.number_input(
    "Expense (%)", 0.0, 1.0, 0.15, step=0.00001, format="%.5f"
)

# ===============================
# INPUT COVERAGE
# ===============================
st.header("📋 Input Coverage")

rows = st.session_state.get("rows", [0])

data = []

for i in rows:
    st.subheader(f"Coverage #{i+1}")

    col1, col2, col3 = st.columns(3)

    with col1:
        coverage = st.selectbox(
            "Coverage", COVERAGE_LIST, key=f"cov_{i}"
        )
        rate = st.number_input(
            "Rate (%)", value=0.0, step=0.00001, format="%.5f", key=f"rate_{i}"
        )
        tsi = st.number_input(
            "TSI IDR", value=0.0, format="%.0f", key=f"tsi_{i}"
        )
        top_risk = st.number_input(
            "Top Risk (IDR)", value=0.0, format="%.0f", key=f"top_{i}"
        )

    with col2:
        askr = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"askr_{i}")
        fak = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fak_{i}")
        lol = st.number_input("% LOL", 0.0, 100.0, 0.0, key=f"lol_{i}")

    with col3:
        kom_fak = st.number_input("% Komisi Fakultatif", 0.0, 100.0, 0.0, key=f"kom_{i}")
        akuisisi = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"akui_{i}")

    data.append({
        "Coverage": coverage,
        "Rate": rate / 100,
        "TSI": tsi,
        "TopRisk": top_risk,
        "LOL": lol / 100,
        "Askrindo": askr / 100,
        "Fakultatif": fak / 100,
        "KomFak": kom_fak / 100,
        "Akuisisi": akuisisi / 100
    })

if st.button("➕ Tambah Coverage"):
    rows.append(len(rows))
    st.session_state["rows"] = rows

# ===============================
# CALCULATION
# ===============================
if st.button("🚀 Calculate"):

    results = []

    for d in data:
        m = MASTER[d["Coverage"]]

        # Exposure
        exposure = d["TSI"] * (d["LOL"] if d["LOL"] > 0 else 1)
        if d["TopRisk"] > 0:
            exposure = min(exposure, d["TopRisk"])

        tsi_askr = d["Askrindo"] * exposure
        exposure_or = min(tsi_askr, m["OR_Cap"])

        tsi_pool = min(
            m["%pool"] * exposure_or,
            (m["Amount_Pool"] or 0) * d["Askrindo"]
        )

        tsi_fac = d["Fakultatif"] * exposure
        tsi_or = exposure_or - tsi_pool - tsi_fac

        # Premi
        prem_100 = d["Rate"] * exposure
        prem_askr = d["Askrindo"] * prem_100
        prem_pool = (tsi_pool / exposure_or) * prem_100 if exposure_or > 0 else 0
        prem_fac = d["Fakultatif"] * prem_100
        prem_or = (tsi_or / exposure_or) * prem_100 if exposure_or > 0 else 0

        # EL
        if pd.notna(m["Rate_Min"]):
            el_100 = m["Rate_Min"] * exposure * LOSS_RATIO
        else:
            el_100 = LOSS_RATIO * prem_100

        el_askr = d["Askrindo"] * el_100
        el_pool = (tsi_pool / exposure_or) * el_100 if exposure_or > 0 else 0
        el_fac = d["Fakultatif"] * el_100

        # Costs
        acq = d["Akuisisi"] * prem_askr
        kom_pool = m["Komisi_Pool"] * prem_pool
        kom_fac = d["KomFak"] * prem_fac
        prem_xol = XOL_RATE * prem_or
        expense = EXPENSE_RATE * prem_askr

        result = (
            prem_askr
            - acq
            - prem_pool
            - prem_fac
            + kom_pool
            + kom_fac
            - el_askr
            + el_pool
            + el_fac
            - prem_xol
            - expense
        )

        results.append({
            "Coverage": d["Coverage"],
            "Prem_Askrindo": prem_askr,
            "Prem_OR": prem_or,
            "Prem_POOL": prem_pool,
            "EL_Askrindo": el_askr,
            "EL_POOL": el_pool,
            "Prem_XOL": prem_xol,
            "Expense": expense,
            "Result": result,
            "%Result": result / prem_askr if prem_askr != 0 else 0
        })

    df = pd.DataFrame(results)
    total = df.select_dtypes("number").sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, total.to_frame().T], ignore_index=True)

    st.header("📈 Hasil Profitability")
    st.dataframe(df.style.format({
        "Prem_Askrindo": "{:,.0f}",
        "Prem_OR": "{:,.0f}",
        "Prem_POOL": "{:,.0f}",
        "EL_Askrindo": "{:,.0f}",
        "EL_POOL": "{:,.0f}",
        "Prem_XOL": "{:,.0f}",
        "Expense": "{:,.0f}",
        "Result": "{:,.0f}",
        "%Result": "{:.2%}"
    }))
