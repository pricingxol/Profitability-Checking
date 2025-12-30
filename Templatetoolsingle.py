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
st.caption("Actuary Profitability Model")

# =====================================================
# LOAD MASTER EXCEL (SINGLE SOURCE OF TRUTH)
# =====================================================
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE)
df_master.columns = df_master.columns.str.strip()

REQUIRED_COLS = [
    "Coverage",
    "Rate_Min",
    "OR_Cap",
    "%pool",
    "Amount_Pool",
    "Komisi_Pool"
]

missing_cols = [c for c in REQUIRED_COLS if c not in df_master.columns]
if missing_cols:
    st.error(f"Kolom berikut tidak ditemukan di Master Excel: {missing_cols}")
    st.stop()

MASTER = df_master.set_index("Coverage")
coverage_list = MASTER.index.tolist()

# =====================================================
# SIDEBAR – ASSUMPTIONS
# =====================================================
st.sidebar.header("📊 Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    min_value=0.0,
    max_value=1.0,
    value=0.40000,
    format="%.5f"
)

XOL_RATE = st.sidebar.number_input(
    "Premi XOL (% dari Premi OR)",
    min_value=0.0,
    max_value=1.0,
    value=0.14070,
    format="%.5f"
)

EXP_RATIO = st.sidebar.number_input(
    "Expense Ratio",
    min_value=0.0,
    max_value=1.0,
    value=0.15000,
    format="%.5f"
)

# =====================================================
# POLICY INFO
# =====================================================
st.markdown("### 📄 Informasi Polis")

cA, cB, cC = st.columns(3)
insured = cA.text_input("Nama Tertanggung", "")
start_date = cB.date_input("Periode Mulai")
end_date = cC.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE
# =====================================================
st.markdown("### 📋 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = [{}]

def add_row():
    st.session_state.rows.append({})

def delete_row(i):
    st.session_state.rows.pop(i)
    st.experimental_rerun()

inputs = []

for i in range(len(st.session_state.rows)):

    st.markdown(f"#### Coverage #{i+1}")

    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

    with c1:
        coverage = st.selectbox("Coverage", coverage_list, key=f"cov_{i}")

        rate_pct = st.number_input(
            "Rate (%)",
            format="%.5f",
            key=f"rate_{i}"
        )
        rate = rate_pct / 100

        tsi_raw = st.text_input(
            "TSI IDR",
            key=f"tsi_{i}",
            help="Input angka penuh tanpa koma"
        )
        try:
            tsi = float(tsi_raw)
        except:
            tsi = 0.0

        top_risk_raw = st.text_input(
            "Top Risk (IDR)",
            key=f"toprisk_{i}",
            help="Opsional, tidak dipakai untuk EL"
        )
        try:
            top_risk = float(top_risk_raw)
        except:
            top_risk = 0.0

    with c2:
        st.markdown("**Share Structure**")
        ask = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}") / 100
        fac = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}") / 100

        lol_premi = st.number_input(
            "% LOL Premi",
            0.0,
            100.0,
            100.0,
            format="%.5f",
            key=f"lolprem_{i}"
        ) / 100

        lol_claim_raw = st.text_input(
            "LOL Klaim (IDR)",
            key=f"lolclaim_{i}",
            help="Isi jika ada limit klaim"
        )
        try:
            lol_claim = float(lol_claim_raw)
        except:
            lol_claim = 0.0

    with c3:
        st.markdown("**Cost Structure**")
        kom_fak = st.number_input("% Komisi Fakultatif", 0.0, 100.0, 0.0, key=f"komf_{i}") / 100
        acq = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"acq_{i}") / 100

    with c4:
        st.write("")
        if st.button("🗑️", key=f"del_{i}"):
            delete_row(i)

    inputs.append({
        "Coverage": coverage,
        "Rate": rate,
        "TSI": tsi,
        "TopRisk": top_risk,
        "ASK": ask,
        "FAC": fac,
        "LOL_Premi": lol_premi,
        "LOL_Claim": lol_claim,
        "KOM_FAK": kom_fak,
        "ACQ": acq
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CORE CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    results = []

    for r in inputs:

        if r["TSI"] <= 0:
            continue

        m = MASTER.loc[r["Coverage"]]

        rate_min = m["Rate_Min"]
        OR_CAP = m["OR_Cap"]
        pool_rate = m["%pool"]
        pool_cap = m["Amount_Pool"]
        kom_pool = m["Komisi_Pool"]

        TSI100 = r["TSI"]

        # ===== PREMIUM =====
        Premi100 = r["Rate"] * TSI100 * r["LOL_Premi"]

        # ===== EXPOSURE FOR SPREADING =====
        TSI_Askrindo = r["ASK"] * TSI100

        TSI_POOL = min(
            pool_rate * TSI_Askrindo,
            pool_cap * r["ASK"]
        )

        TSI_Fak = r["FAC"] * TSI100

        TSI_OR = max(TSI_Askrindo - TSI_POOL - TSI_Fak, 0)
        Exposure_OR = min(TSI_OR, OR_CAP)

        # ===== PREMIUM SPLIT =====
        Prem_Askrindo = Premi100 * (TSI_Askrindo / TSI100)
        Prem_POOL = Premi100 * (TSI_POOL / TSI100)
        Prem_Fak = Premi100 * (TSI_Fak / TSI100)
        Prem_OR = Premi100 * (Exposure_OR / TSI100)

        # ===== EL BASIS =====
        if r["LOL_Claim"] > 0:
            EL_Basis = r["LOL_Claim"]
        else:
            EL_Basis = TSI100

        # ===== EL 100 =====
        if pd.isna(rate_min):
            EL100 = LOSS_RATIO * Premi100
        else:
            EL100 = rate_min * EL_Basis * LOSS_RATIO

        # ===== EL SPLIT =====
        EL_Askrindo = EL100 * (TSI_Askrindo / EL_Basis)
        EL_POOL = EL100 * (TSI_POOL / EL_Basis)
        EL_Fak = EL100 * (TSI_Fak / EL_Basis)

        # ===== COST =====
        Akuisisi = r["ACQ"] * Prem_Askrindo
        Kom_POOL = kom_pool * Prem_POOL
        Kom_Fak = r["KOM_FAK"] * Prem_Fak
        Prem_XOL = XOL_RATE * Prem_OR
        Expense = EXP_RATIO * Prem_Askrindo

        # ===== RESULT =====
        Result = (
            Prem_Askrindo
            - Akuisisi
            - Prem_POOL
            - Prem_Fak
            + Kom_POOL
            + Kom_Fak
            - EL_Askrindo
            + EL_POOL
            + EL_Fak
            - Prem_XOL
            - Expense
        )

        results.append({
            "Coverage": r["Coverage"],
            "Prem_Askrindo": Prem_Askrindo,
            "Prem_POOL": Prem_POOL,
            "Prem_OR": Prem_OR,
            "EL_Askrindo": EL_Askrindo,
            "EL_POOL": EL_POOL,
            "Prem_XOL": Prem_XOL,
            "Expense": Expense,
            "Result": Result,
            "%Result": Result / Prem_Askrindo
        })

    df = pd.DataFrame(results)

    total = df.select_dtypes("number").sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.markdown("### 📈 Hasil Profitability")

    st.dataframe(
        df.style
        .format("{:,.0f}", subset=[
            "Prem_Askrindo","Prem_POOL","Prem_OR",
            "EL_Askrindo","EL_POOL",
            "Prem_XOL","Expense","Result"
        ])
        .format("{:.2%}", subset=["%Result"]),
        use_container_width=True
    )
