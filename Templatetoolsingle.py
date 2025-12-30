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
st.caption("Pricing & Profitability Engine – Excel-driven master logic")

# =====================================================
# LOAD MASTER EXCEL (FIXED NAME)
# =====================================================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "master coverage"

df_master = pd.read_excel(MASTER_FILE, sheet_name=MASTER_SHEET)
df_master.columns = df_master.columns.str.strip()

MASTER = df_master.set_index("Coverage").to_dict(orient="index")
COVERAGE_LIST = df_master["Coverage"].tolist()

# =====================================================
# GLOBAL ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    min_value=0.0,
    max_value=1.0,
    value=0.40,
    format="%.5f"
)

XOL_RATE = st.sidebar.number_input(
    "Asumsi Premi XOL",
    min_value=0.0,
    max_value=1.0,
    value=0.1407,
    format="%.5f"
)

EXPENSE_RATE = st.sidebar.number_input(
    "Asumsi Expense",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    format="%.5f"
)

# =====================================================
# SESSION STATE
# =====================================================
if "rows" not in st.session_state:
    st.session_state.rows = [0]

def add_row():
    st.session_state.rows.append(len(st.session_state.rows))

def remove_row(i):
    st.session_state.rows.pop(i)

# =====================================================
# INPUT UI
# =====================================================
st.header("📋 Input Coverage")

inputs = []

for i in st.session_state.rows:
    st.subheader(f"Coverage #{i+1}")

    col1, col2, col3 = st.columns(3)

    with col1:
        coverage = st.selectbox(
            "Coverage",
            COVERAGE_LIST,
            key=f"cov_{i}"
        )

        rate = st.number_input(
            "Rate (%)",
            value=0.0,
            format="%.5f",
            key=f"rate_{i}"
        )

        tsi_raw = st.text_input(
            "TSI IDR",
            placeholder="Masukkan TSI",
            key=f"tsi_{i}"
        )

    with col2:
        askrindo = st.number_input(
            "% Askrindo",
            0.0, 100.0, 10.0,
            format="%.2f",
            key=f"ask_{i}"
        )

        fakultatif = st.number_input(
            "% Fakultatif",
            0.0, 100.0, 0.0,
            format="%.2f",
            key=f"fac_{i}"
        )

        lol_pct = st.number_input(
            "% LOL",
            0.0, 100.0, 100.0,
            format="%.2f",
            key=f"lol_{i}"
        )

    with col3:
        komisi_fac = st.number_input(
            "% Komisi Fakultatif",
            0.0, 100.0, 0.0,
            format="%.2f",
            key=f"komfac_{i}"
        )

        akuisisi = st.number_input(
            "% Akuisisi",
            0.0, 100.0, 15.0,
            format="%.2f",
            key=f"akq_{i}"
        )

        top_raw = st.text_input(
            "Top Risk (IDR)",
            placeholder="Default = TSI",
            key=f"top_{i}"
        )

    if st.button("🗑 Hapus", key=f"del_{i}"):
        remove_row(i)
        st.experimental_rerun()

    inputs.append({
        "Coverage": coverage,
        "Rate": rate / 100,
        "TSI": float(tsi_raw.replace(",", "")) if tsi_raw else 0.0,
        "TopRisk": float(top_raw.replace(",", "")) if top_raw else None,
        "Askrindo": askrindo / 100,
        "Fac": fakultatif / 100,
        "KomFac": komisi_fac / 100,
        "Akuisisi": akuisisi / 100,
        "LOL": lol_pct / 100
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):
    results = []

    for r in inputs:
        m = MASTER[r["Coverage"]]

        TSI = r["TSI"]
        TOP = r["TopRisk"] if r["TopRisk"] else TSI
        LOL_BASE = TSI * r["LOL"]

        TSI_Askrindo = LOL_BASE * r["Askrindo"]

        OR_CAP = m["OR_Cap"]
        Exposure_OR = min(TSI_Askrindo, OR_CAP)

        Pool_amt = min(
            m["%pool"] * TSI_Askrindo,
            (m["Amount_Pool"] or 0) * r["Askrindo"]
        )

        Fac_amt = r["Fac"] * TSI_Askrindo
        OR_amt = max(TSI_Askrindo - Pool_amt - Fac_amt, 0)

        Prem100 = r["Rate"] * TSI * r["LOL"]
        Prem_Askrindo = Prem100 * r["Askrindo"]

        Prem_POOL = Prem100 * (Pool_amt / TSI_Askrindo if TSI_Askrindo > 0 else 0)
        Prem_Fac = Prem100 * r["Fac"]
        Prem_OR = Prem_Askrindo - Prem_POOL - Prem_Fac

        # EL
        if not pd.isna(m["Rate_Min"]):
            EL100 = m["Rate_Min"] * LOSS_RATIO * LOL_BASE
        else:
            EL100 = LOSS_RATIO * Prem100

        EL_Askrindo = EL100 * r["Askrindo"]
        EL_POOL = EL100 * (Pool_amt / TSI_Askrindo if TSI_Askrindo > 0 else 0)

        # COST
        Komisi_POOL = m["Komisi_Pool"] * Prem_POOL
        Komisi_Fac = r["KomFac"] * Prem_Fac
        Akuisisi_amt = r["Akuisisi"] * Prem_Askrindo
        Prem_XOL = XOL_RATE * Prem_OR
        Expense = EXPENSE_RATE * Prem_Askrindo

        Result = (
            Prem_Askrindo
            - Akuisisi_amt
            - Prem_POOL
            - Prem_Fac
            + Komisi_POOL
            + Komisi_Fac
            - EL_Askrindo
            + EL_POOL
            - Prem_XOL
            - Expense
        )

        results.append({
            "Coverage": r["Coverage"],
            "Prem_Askrindo": Prem_Askrindo,
            "Prem_OR": Prem_OR,
            "Prem_POOL": Prem_POOL,
            "EL_Askrindo": EL_Askrindo,
            "EL_POOL": EL_POOL,
            "Prem_XOL": Prem_XOL,
            "Expense": Expense,
            "Result": Result,
            "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
        })

    df = pd.DataFrame(results)

    total = df.sum(numeric_only=True)
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.header("📈 Hasil Profitability")
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
