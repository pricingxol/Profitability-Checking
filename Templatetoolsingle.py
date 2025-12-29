import streamlit as st
import pandas as pd
import numpy as np
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")
st.caption("Versi Excel-driven | Logic match Bulk Profitability")

# =====================================================
# LOAD MASTER EXCEL (JANGAN UBAH NAMA FILE)
# =====================================================
MASTER_FILE = "Master File.xlsx"
df_master = pd.read_excel(MASTER_FILE, sheet_name="MASTER")

df_master.columns = df_master.columns.str.strip()

MASTER = {}
for _, r in df_master.iterrows():
    MASTER[r["Coverage"]] = {
        "rate_min": r["Rate_Min"] if not pd.isna(r["Rate_Min"]) else None,
        "or_cap": r["OR_Cap"],
        "pool_rate": r["%pool"] / 100,
        "pool_cap": r["Amount_Pool"],
        "komisi_pool": r["Komisi_Pool"] / 100,
    }

COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# USER ASSUMPTIONS
# =====================================================
with st.sidebar:
    st.header("Asumsi Profitability")
    loss_ratio = st.number_input("Loss Ratio", 0.0, 1.0, 0.40, 0.01)
    xol_rate = st.number_input("Premi XOL (%)", 0.0, 100.0, 14.07, 0.01) / 100
    expense_rate = st.number_input("Expense (%)", 0.0, 100.0, 15.00, 0.01) / 100

# =====================================================
# POLICY INFO
# =====================================================
st.subheader("📄 Informasi Polis")
c1, c2, c3 = st.columns(3)

insured = c1.text_input("Nama Tertanggung", "")
sdate = c2.date_input("Periode Mulai")
edate = c3.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("🧾 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = []

def add_row():
    st.session_state.rows.append({
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI": 0.0,
        "ask": 10.0,
        "fac": 0.0,
        "kom_fak": 0.0,
        "lol": 100.0,
        "acq": 15.0,
    })

def delete_row(i):
    st.session_state.rows.pop(i)

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# INPUT UI
# =====================================================
for i, r in enumerate(st.session_state.rows):
    with st.container():
        cols = st.columns([2,1,2,1,1,1,1,1,0.5])
        r["Coverage"] = cols[0].selectbox(
            "Coverage", COVERAGE_LIST, index=COVERAGE_LIST.index(r["Coverage"]),
            key=f"cov_{i}"
        )
        r["Rate"] = cols[1].number_input("Rate (%)", value=r["Rate"], format="%.5f", key=f"rate_{i}")
        r["TSI"] = cols[2].number_input("TSI IDR", value=r["TSI"], key=f"tsi_{i}")
        r["ask"] = cols[3].number_input("% Askrindo", value=r["ask"], key=f"ask_{i}")
        r["fac"] = cols[4].number_input("% Fakultatif", value=r["fac"], key=f"fac_{i}")
        r["kom_fak"] = cols[5].number_input("% Komisi Fak", value=r["kom_fak"], key=f"kom_{i}")
        r["lol"] = cols[6].number_input("% LOL", value=r["lol"], key=f"lol_{i}")
        r["acq"] = cols[7].number_input("% Akuisisi", value=r["acq"], key=f"acq_{i}")
        cols[8].button("🗑️", key=f"del_{i}", on_click=delete_row, args=(i,))

# =====================================================
# CORE CALCULATION
# =====================================================
def calculate(row):
    m = MASTER[row["Coverage"]]

    rate = row["Rate"] / 100
    TSI100 = row["TSI"]
    ask = row["ask"] / 100
    fac = row["fac"] / 100
    lol = row["lol"] / 100
    acq = row["acq"] / 100

    Prem100 = rate * lol * TSI100
    EL100 = (m["rate_min"] if m["rate_min"] else rate) * loss_ratio * TSI100

    TSI_Askrindo = ask * TSI100
    TSI_Pool = min(m["pool_rate"] * TSI_Askrindo, m["pool_cap"] * ask)
    TSI_Fac = fac * TSI100
    TSI_OR = max(TSI_Askrindo - TSI_Pool - TSI_Fac, 0)

    Prem_Askrindo = ask * Prem100
    Prem_OR = Prem100 * (TSI_OR / TSI100 if TSI100 else 0)
    Prem_Pool = Prem100 * (TSI_Pool / TSI100 if TSI100 else 0)

    EL_Askrindo = ask * EL100
    EL_Pool = EL100 * (TSI_Pool / TSI100 if TSI100 else 0)

    XOL = xol_rate * Prem_OR
    Expense = expense_rate * Prem_Askrindo
    Kom_Pool = m["komisi_pool"] * Prem_Pool
    Acq = acq * Prem_Askrindo

    Result = (
        Prem_Askrindo
        - Prem_Pool
        - Acq
        + Kom_Pool
        - EL_Askrindo
        + EL_Pool
        - XOL
        - Expense
    )

    return {
        "Coverage": row["Coverage"],
        "Prem_Askrindo": Prem_Askrindo,
        "Prem_OR": Prem_OR,
        "Prem_POOL": Prem_Pool,
        "EL_Askrindo": EL_Askrindo,
        "EL_POOL": EL_Pool,
        "Prem_XOL": XOL,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
    }

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    results = pd.DataFrame([calculate(r) for r in st.session_state.rows])

    total = results.select_dtypes("number").sum()
    total["Coverage"] = "TOTAL"
    results = pd.concat([results, total.to_frame().T], ignore_index=True)

    fmt = {
        c: "{:,.0f}" for c in results.columns if c not in ["Coverage", "%Result"]
    }
    fmt["%Result"] = "{:.2%}"

    st.subheader("📈 Hasil Profitability")
    st.dataframe(results.style.format(fmt), use_container_width=True)

