import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")
st.caption("Versi Excel-driven | Logic match Master Excel")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
MASTER_FILE = "Master File.xlsx"  # pastikan file ada di folder app

df_master = pd.read_excel(MASTER_FILE)

# normalisasi kolom
df_master.columns = df_master.columns.str.strip()

MASTER = (
    df_master
    .set_index("Coverage")
    .to_dict(orient="index")
)

COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# USER ASSUMPTIONS
# =====================================================
st.sidebar.header("📌 Asumsi Profitability")

loss_ratio = st.sidebar.number_input(
    "Asumsi Loss Ratio", min_value=0.0, max_value=1.0, value=0.40, step=0.01
)

xol_rate = st.sidebar.number_input(
    "Asumsi Premi XOL (%)", min_value=0.0, max_value=100.0, value=14.07, step=0.01
) / 100

expense_rate = st.sidebar.number_input(
    "Asumsi Expense (%)", min_value=0.0, max_value=100.0, value=15.00, step=0.01
) / 100

# =====================================================
# INFORMASI POLIS
# =====================================================
st.header("📄 Informasi Polis")

c1, c2, c3 = st.columns(3)
with c1:
    insured_name = st.text_input("Nama Tertanggung", value="")
with c2:
    start_date = st.date_input("Periode Mulai")
with c3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE (SESSION SAFE)
# =====================================================
st.header("🧾 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = []

def add_row():
    st.session_state.rows.append({
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI": 0.0,
        "Askrindo": 10.0,
        "Fac": 0.0,
        "KomisiFac": 0.0,
        "LOL": 100.0,
        "Akuisisi": 15.0
    })

def delete_row(i):
    st.session_state.rows.pop(i)

if st.button("➕ Tambah Coverage"):
    add_row()

for i, row in enumerate(st.session_state.rows):
    c = st.columns([2,1,2,1,1,1,1,1,0.4])

    row["Coverage"] = c[0].selectbox(
        "Coverage", COVERAGE_LIST,
        index=COVERAGE_LIST.index(row["Coverage"]),
        key=f"cov_{i}"
    )
    row["Rate"] = c[1].number_input("Rate (%)", value=row["Rate"], step=0.01, key=f"r_{i}")
    row["TSI"] = c[2].number_input("TSI IDR", value=row["TSI"], step=1.0, key=f"tsi_{i}")
    row["Askrindo"] = c[3].number_input("% Askrindo", value=row["Askrindo"], step=1.0, key=f"a_{i}")
    row["Fac"] = c[4].number_input("% Fakultatif", value=row["Fac"], step=1.0, key=f"f_{i}")
    row["KomisiFac"] = c[5].number_input("% Komisi Fak", value=row["KomisiFac"], step=1.0, key=f"kf_{i}")
    row["LOL"] = c[6].number_input("% LOL", value=row["LOL"], step=1.0, key=f"lol_{i}")
    row["Akuisisi"] = c[7].number_input("% Akuisisi", value=row["Akuisisi"], step=1.0, key=f"ak_{i}")

    if c[8].button("🗑️", key=f"del_{i}"):
        delete_row(i)
        st.rerun()

# =====================================================
# CORE ENGINE (FINAL LOGIC)
# =====================================================
def run_profitability(row):

    cfg = MASTER[row["Coverage"]]

    TSI100 = row["TSI"]
    rate = row["Rate"] / 100
    lol = row["LOL"] / 100

    a = row["Askrindo"] / 100
    f = row["Fac"] / 100
    p = cfg["%pool"] / 100 if cfg["%pool"] > 0 else 0.0

    pool_cap = cfg["Amount_Pool"]
    komisi_pool = cfg["Komisi_Pool"] / 100

    # =========================
    # TSI SPLIT (FINAL)
    # =========================
    TSI_Askrindo = a * TSI100
    TSI_Pool = min(p * TSI_Askrindo, pool_cap * a)
    TSI_Fac = f * TSI100
    TSI_OR = TSI_Askrindo - TSI_Pool - TSI_Fac

    # =========================
    # PREMIUM
    # =========================
    Prem100 = rate * lol * TSI100

    Prem_Askrindo = Prem100 * (TSI_Askrindo / TSI100)
    Prem_POOL = Prem100 * (TSI_Pool / TSI100)
    Prem_Fac = Prem100 * (TSI_Fac / TSI100)
    Prem_OR = Prem100 * (TSI_OR / TSI100)

    # =========================
    # EL
    # =========================
    rate_min = cfg["Rate_Min"] if not pd.isna(cfg["Rate_Min"]) else rate
    EL100 = rate_min * loss_ratio * TSI100

    EL_Askrindo = EL100 * (TSI_Askrindo / TSI100)
    EL_POOL = EL100 * (TSI_Pool / TSI100)
    EL_Fac = EL100 * (TSI_Fac / TSI100)

    # =========================
    # COST
    # =========================
    Prem_XOL = xol_rate * Prem_OR
    Expense = expense_rate * Prem_Askrindo
    Akuisisi = (row["Akuisisi"] / 100) * Prem_Askrindo

    # =========================
    # RESULT
    # =========================
    Result = (
        Prem_Askrindo
        - Prem_POOL
        - Prem_Fac
        - Akuisisi
        + komisi_pool * Prem_POOL
        + (row["KomisiFac"] / 100) * Prem_Fac
        - EL_Askrindo
        + EL_POOL
        + EL_Fac
        - Prem_XOL
        - Expense
    )

    return {
        "Coverage": row["Coverage"],
        "Prem_Askrindo": Prem_Askrindo,
        "Prem_OR": Prem_OR,
        "EL_Askrindo": EL_Askrindo,
        "Prem_XOL": Prem_XOL,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo != 0 else 0
    }

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate") and st.session_state.rows:

    results = [run_profitability(r) for r in st.session_state.rows]
    df = pd.DataFrame(results)

    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.header("📈 Hasil Profitability")

    st.dataframe(
        df.style.format({
            "Prem_Askrindo": "{:,.0f}",
            "Prem_OR": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "Prem_XOL": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )
