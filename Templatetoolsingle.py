import streamlit as st
import pandas as pd
import numpy as np
import os

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
# LOAD MASTER (TANPA HARDCODE SHEET)
# =====================================================
MASTER_FILE = "Master File.xlsx"

if not os.path.exists(MASTER_FILE):
    st.error("❌ Master File.xlsx tidak ditemukan")
    st.stop()

xls = pd.ExcelFile(MASTER_FILE)
df_master = pd.read_excel(xls, xls.sheet_names[0])
df_master.columns = df_master.columns.str.strip()

REQUIRED_COLS = [
    "Coverage",
    "OR_Cap",
    "Pool_Rate",
    "Pool_Cap",
    "Komisi_Pool",
    "Rate_Min"
]

missing = [c for c in REQUIRED_COLS if c not in df_master.columns]
if missing:
    st.error(f"❌ Kolom MASTER kurang: {missing}")
    st.stop()

MASTER = df_master.set_index("Coverage").to_dict("index")
COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# SIDEBAR ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE   = st.sidebar.number_input("Asumsi Premi XOL", 0.0, 1.0, 0.1407, 0.001)
EXP_RATE   = st.sidebar.number_input("Asumsi Expense", 0.0, 1.0, 0.15, 0.01)

# =====================================================
# POLICY INFO
# =====================================================
st.subheader("📄 Informasi Polis")
col1, col2, col3 = st.columns(3)

with col1:
    nama_tertanggung = st.text_input("Nama Tertanggung", "")

with col2:
    sdate = st.date_input("Periode Mulai")

with col3:
    edate = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("🧾 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = [{}]

def add_row():
    st.session_state.rows.append({})

def delete_row(i):
    st.session_state.rows.pop(i)

for i, row in enumerate(st.session_state.rows):
    c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([2,1,2,1,1,1,1,1,0.5])

    with c1:
        cov = st.selectbox("Coverage", COVERAGE_LIST, key=f"cov_{i}")

    with c2:
        rate = st.number_input("Rate (%)", value=0.0, format="%.5f", key=f"rate_{i}") / 100

    with c3:
        tsi = st.text_input("TSI IDR", value="", key=f"tsi_{i}")
        tsi = float(tsi) if tsi else 0.0

    with c4:
        ask = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}") / 100

    with c5:
        fak = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fak_{i}") / 100

    with c6:
        kom_fak = st.number_input("% Komisi Fak", 0.0, 100.0, 0.0, key=f"komfak_{i}") / 100

    with c7:
        lol = st.number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}") / 100

    with c8:
        akq = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"akq_{i}") / 100

    with c9:
        st.button("🗑️", key=f"del_{i}", on_click=delete_row, args=(i,))

    row.update(dict(
        Coverage=cov, Rate=rate, TSI=tsi, Askrindo=ask,
        Fak=fak, KomFak=kom_fak, LOL=lol, Akq=akq
    ))

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):
    results = []

    for r in st.session_state.rows:
        m = MASTER[r["Coverage"]]

        TSI100 = r["TSI"]
        Prem100 = r["Rate"] * r["LOL"] * TSI100

        TSI_Askr = r["Askrindo"] * TSI100
        TSI_Pool = min(m["Pool_Rate"] * TSI_Askr, m["Pool_Cap"] * r["Askrindo"])
        TSI_Fak  = r["Fak"] * TSI100
        TSI_OR   = TSI_Askr - TSI_Pool - TSI_Fak

        Exposure_OR = min(TSI_Askr, m["OR_Cap"])

        Prem_Askr = Prem100 * r["Askrindo"]
        Prem_POOL = Prem100 * (TSI_Pool / TSI100 if TSI100 else 0)
        Prem_Fak  = Prem100 * r["Fak"]
        Prem_OR   = Prem100 * (TSI_OR / TSI100 if TSI100 else 0)
        Prem_XOL  = XOL_RATE * Prem_OR

        if not pd.isna(m["Rate_Min"]):
            EL100 = m["Rate_Min"] * LOSS_RATIO * TSI100 * r["LOL"]
        else:
            EL100 = LOSS_RATIO * Prem100

        EL_Askr = EL100 * r["Askrindo"]
        EL_POOL = EL100 * (TSI_Pool / TSI100 if TSI100 else 0)
        EL_Fak  = EL100 * r["Fak"]

        Akuisisi = r["Akq"] * Prem_Askr
        Kom_POOL = m["Komisi_Pool"] * Prem_POOL
        Kom_Fak  = r["KomFak"] * Prem_Fak
        Expense  = EXP_RATE * Prem_Askr

        Result = (
            Prem_Askr
            - Akuisisi
            - Prem_POOL
            - Prem_Fak
            + Kom_POOL
            + Kom_Fak
            - EL_Askr
            + EL_POOL
            + EL_Fak
            - Prem_XOL
            - Expense
        )

        results.append([
            r["Coverage"],
            Prem_Askr, Prem_OR, Prem_POOL,
            EL_Askr, EL_POOL,
            Prem_XOL, Expense,
            Result, Result / Prem_Askr if Prem_Askr else 0
        ])

    df = pd.DataFrame(results, columns=[
        "Coverage","Prem_Askrindo","Prem_OR","Prem_POOL",
        "EL_Askrindo","EL_POOL","Prem_XOL","Expense",
        "Result","%Result"
    ])

    total = df.drop(columns=["Coverage"]).sum()
    total["Coverage"] = "TOTAL"
    df = pd.concat([df, pd.DataFrame([total])])

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df.style.format({
            c: "{:,.0f}" for c in df.columns if c not in ["Coverage","%Result"]
        } | {"%Result": "{:.2%}"}
    )
