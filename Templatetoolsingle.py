import streamlit as st
import pandas as pd
import numpy as np

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
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE, sheet_name="MASTER")
df_master.columns = df_master.columns.str.strip()

MASTER = (
    df_master
    .set_index("Coverage")
    .to_dict(orient="index")
)

COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# ASUMSI (SIDEBAR)
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    min_value=0.0, max_value=1.0,
    value=0.40, step=0.01
)

XOL_RATE = st.sidebar.number_input(
    "Asumsi Premi XOL (%)",
    min_value=0.0, max_value=100.0,
    value=14.07, step=0.01
) / 100

EXPENSE_RATE = st.sidebar.number_input(
    "Asumsi Expense (%)",
    min_value=0.0, max_value=100.0,
    value=15.00, step=0.01
) / 100

# =====================================================
# SESSION STATE
# =====================================================
if "rows" not in st.session_state:
    st.session_state.rows = []

# =====================================================
# ADD ROW
# =====================================================
def add_row():
    st.session_state.rows.append({
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI": 0.0,
        "ask": 10.0,
        "fac": 0.0,
        "kom_fac": 0.0,
        "lol": 100.0,
        "acq": 15.0
    })

def delete_row(i):
    st.session_state.rows.pop(i)

# =====================================================
# INPUT UI
# =====================================================
st.subheader("🧾 Input Coverage")

if st.button("➕ Tambah Coverage"):
    add_row()

for i, r in enumerate(st.session_state.rows):
    c1,c2,c3,c4,c5,c6,c7,c8,c9 = st.columns([2,1,2,1,1,1,1,1,0.5])

    r["Coverage"] = c1.selectbox(
        "Coverage",
        COVERAGE_LIST,
        index=COVERAGE_LIST.index(r["Coverage"]),
        key=f"cov{i}"
    )

    r["Rate"] = c2.number_input(
        "Rate (%)",
        value=r["Rate"],
        step=0.00001,
        format="%.5f",
        key=f"rate{i}"
    )

    r["TSI"] = c3.number_input(
        "TSI IDR",
        value=r["TSI"],
        format="%.0f",
        key=f"tsi{i}"
    )

    r["ask"] = c4.number_input("% Askrindo", value=r["ask"], step=1.0, key=f"ask{i}")
    r["fac"] = c5.number_input("% Fakultatif", value=r["fac"], step=1.0, key=f"fac{i}")
    r["kom_fac"] = c6.number_input("% Komisi Fak", value=r["kom_fac"], step=1.0, key=f"kom{i}")
    r["lol"] = c7.number_input("% LOL", value=r["lol"], step=1.0, key=f"lol{i}")
    r["acq"] = c8.number_input("% Akuisisi", value=r["acq"], step=1.0, key=f"acq{i}")

    if c9.button("🗑️", key=f"del{i}"):
        delete_row(i)
        st.experimental_rerun()

# =====================================================
# CORE ENGINE
# =====================================================
def run_profitability(r):
    m = MASTER[r["Coverage"]]

    rate = r["Rate"] / 100
    tsi100 = r["TSI"]
    ask = r["ask"] / 100
    fac = r["fac"] / 100
    lol = r["lol"] / 100
    acq = r["acq"] / 100

    # --- TSI SPLIT (FINAL LOGIC) ---
    TSI_Askrindo = ask * tsi100

    pool_rate = m["%pool"] if not pd.isna(m["%pool"]) else 0
    pool_cap = m["Amount_Pool"] if not pd.isna(m["Amount_Pool"]) else 0
    kom_pool = m["Komisi_Pool"] if not pd.isna(m["Komisi_Pool"]) else 0

    TSI_Pool = min(pool_rate * TSI_Askrindo, pool_cap * ask)
    TSI_Fac = fac * tsi100
    TSI_OR = max(TSI_Askrindo - TSI_Pool - TSI_Fac, 0)

    OR_CAP = m["OR_Cap"]
    Exposure_OR = min(TSI_Askrindo, OR_CAP)

    # --- PREMIUM ---
    Prem100 = rate * lol * tsi100
    Prem_Askrindo = ask * Prem100
    Prem_POOL = Prem100 * (TSI_Pool / tsi100) if tsi100 else 0
    Prem_Fac = Prem100 * fac
    Prem_OR = Prem100 * (Exposure_OR / tsi100) if tsi100 else 0

    # --- COMMISSION ---
    Acq_amt = acq * Prem_Askrindo
    Kom_POOL = kom_pool * Prem_POOL
    Kom_Fac = (r["kom_fac"]/100) * Prem_Fac

    # --- EL ---
    if not pd.isna(m["Rate_Min"]):
        EL100 = m["Rate_Min"] * LOSS_RATIO * tsi100 * lol
    else:
        EL100 = LOSS_RATIO * Prem100

    EL_Askrindo = ask * EL100
    EL_POOL = EL100 * (TSI_Pool / tsi100) if tsi100 else 0
    EL_Fac = fac * EL100

    # --- COST ---
    Prem_XOL = XOL_RATE * Prem_OR
    Expense = EXPENSE_RATE * Prem_Askrindo

    # --- RESULT (FINAL FORMULA) ---
    Result = (
        Prem_Askrindo
        - Acq_amt
        - Prem_POOL
        - Prem_Fac
        + Kom_POOL
        + Kom_Fac
        - EL_Askrindo
        + EL_POOL
        + EL_Fac
        - Prem_XOL
        - Expense
    )

    return {
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
    }

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate") and st.session_state.rows:
    results = [run_profitability(r) for r in st.session_state.rows]
    df = pd.DataFrame(results)

    total = df.drop(columns=["Coverage","%Result"]).sum()
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
