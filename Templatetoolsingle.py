import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

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
# LOAD MASTER EXCEL (JANGAN UBAH NAMA FILE)
# =====================================================
MASTER_FILE = "Master File.xlsx"

@st.cache_data
def load_master():
    df = pd.read_excel(MASTER_FILE)
    df.columns = [c.strip() for c in df.columns]
    return df

df_master = load_master()

# =====================================================
# MASTER DICT
# =====================================================
MASTER = {}
for _, r in df_master.iterrows():
    MASTER[r["Coverage"]] = {
        "rate_min": r["Rate_Min"],
        "or_cap": r["OR_Cap"],
        "pool_rate": r["%pool"],
        "pool_cap": r["Amount_Pool"],
        "komisi_pool": r["Komisi_Pool"],
    }

COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# ASSUMSI
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE   = st.sidebar.number_input("Asumsi Premi XOL (%)", 0.0, 100.0, 14.07, 0.01) / 100
EXP_RATIO  = st.sidebar.number_input("Asumsi Expense (%)", 0.0, 100.0, 15.0, 0.01) / 100

# =====================================================
# INFORMASI POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

c1, c2, c3 = st.columns(3)
with c1:
    insured_name = st.text_input("Nama Tertanggung", "")
with c2:
    sdate = st.date_input("Periode Mulai", date.today())
with c3:
    edate = st.date_input("Periode Akhir", date.today())

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("🧾 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = [0]

def add_row():
    st.session_state.rows.append(len(st.session_state.rows))

def delete_row(i):
    st.session_state.rows.pop(i)

input_rows = []

for i in range(len(st.session_state.rows)):
    cols = st.columns([2,1,2,1,1,1,1,1,0.3])

    with cols[0]:
        cov = st.selectbox("Coverage", COVERAGE_LIST, key=f"cov_{i}")
    with cols[1]:
        rate = st.number_input("Rate (%)", value=0.0, format="%.5f", key=f"rate_{i}")
    with cols[2]:
        tsi = st.number_input("TSI IDR", value=0.0, format="%.0f", key=f"tsi_{i}")
    with cols[3]:
        ask = st.number_input("% Askrindo", value=10.0, key=f"ask_{i}") / 100
    with cols[4]:
        fac = st.number_input("% Fakultatif", value=0.0, key=f"fac_{i}") / 100
    with cols[5]:
        kom_f = st.number_input("% Komisi Fak", value=0.0, key=f"komf_{i}") / 100
    with cols[6]:
        lol = st.number_input("% LOL", value=100.0, key=f"lol_{i}") / 100
    with cols[7]:
        aq = st.number_input("% Akuisisi", value=15.0, key=f"aq_{i}") / 100
    with cols[8]:
        if st.button("🗑️", key=f"del_{i}"):
            delete_row(i)
            st.experimental_rerun()

    input_rows.append({
        "Coverage": cov,
        "Rate": rate / 100,
        "TSI": tsi,
        "Ask": ask,
        "Fac": fac,
        "KomF": kom_f,
        "LOL": lol,
        "Aq": aq
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    results = []

    for r in input_rows:

        m = MASTER[r["Coverage"]]

        # ===== TSI SPLIT (FINAL LOGIC) =====
        TSI_ASK  = r["Ask"] * r["TSI"]
        TSI_POOL = min(
            m["pool_rate"] * TSI_ASK,
            m["pool_cap"] * r["Ask"]
        )
        TSI_FAC  = r["Fac"] * r["TSI"]
        TSI_OR   = max(TSI_ASK - TSI_POOL - TSI_FAC, 0)

        # ===== PREMI =====
        Prem100 = r["Rate"] * r["LOL"] * r["TSI"]

        Prem_Ask  = Prem100 * r["Ask"]
        Prem_POOL = Prem100 * (TSI_POOL / r["TSI"]) if r["TSI"] > 0 else 0
        Prem_FAC  = Prem100 * r["Fac"]
        Prem_OR   = Prem100 * (TSI_OR / r["TSI"]) if r["TSI"] > 0 else 0

        # ===== KOMISI =====
        Aq_amt    = r["Aq"] * Prem_Ask
        Kom_POOL  = m["komisi_pool"] * Prem_POOL
        Kom_FAC   = r["KomF"] * Prem_FAC

        # ===== EL =====
        EL100 = LOSS_RATIO * Prem100
        EL_Ask  = EL100 * r["Ask"]
        EL_POOL = EL100 * (TSI_POOL / r["TSI"]) if r["TSI"] > 0 else 0
        EL_FAC  = EL100 * r["Fac"]

        # ===== COST =====
        Prem_XOL = XOL_RATE * Prem_OR
        Expense  = EXP_RATIO * Prem_Ask

        # ===== RESULT (FINAL & LOCKED) =====
        Result = (
            Prem_Ask
            - Aq_amt
            - Prem_POOL
            - Prem_FAC
            + Kom_POOL
            + Kom_FAC
            - EL_Ask
            + EL_POOL
            + EL_FAC
            - Prem_XOL
            - Expense
        )

        results.append({
            "Coverage": r["Coverage"],
            "Prem_Askrindo": Prem_Ask,
            "Prem_OR": Prem_OR,
            "Prem_POOL": Prem_POOL,
            "EL_Askrindo": EL_Ask,
            "EL_POOL": EL_POOL,
            "Prem_XOL": Prem_XOL,
            "Expense": Expense,
            "Result": Result,
            "%Result": Result / Prem_Ask if Prem_Ask != 0 else 0
        })

    df = pd.DataFrame(results)

    total = df.drop(columns=["Coverage","%Result"]).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"] if total["Prem_Askrindo"] != 0 else 0

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    # =====================================================
    # DISPLAY
    # =====================================================
    st.subheader("📈 Hasil Profitability")

    fmt = {c: "{:,.0f}" for c in df.columns if c not in ["Coverage", "%Result"]}
    fmt["%Result"] = "{:.2%}"

    st.dataframe(
        df.style.format(fmt),
        use_container_width=True
    )
