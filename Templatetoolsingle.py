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
st.caption("Logic aligned with actuarial underwriting & bulk profitability model")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE)
df_master.columns = df_master.columns.str.strip()

MASTER = df_master.set_index("Coverage")

COVERAGE_LIST = MASTER.index.tolist()

# =====================================================
# GLOBAL ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Global")

LOSS_RATIO = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    min_value=0.0,
    max_value=1.0,
    value=0.40,
    step=0.00001,
    format="%.5f"
)

XOL_RATE = st.sidebar.number_input(
    "Asumsi Premi XOL",
    min_value=0.0,
    max_value=1.0,
    value=0.1407,
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
# SESSION STATE
# =====================================================
if "coverages" not in st.session_state:
    st.session_state.coverages = [0]

def add_coverage():
    st.session_state.coverages.append(len(st.session_state.coverages))

def remove_coverage(idx):
    st.session_state.coverages.pop(idx)

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("📋 Input Coverage")

inputs = []

for i, idx in enumerate(st.session_state.coverages):

    st.markdown(f"### Coverage #{i+1}")
    col1, col2, col3 = st.columns(3)

    with col1:
        coverage = st.selectbox(
            "Coverage",
            COVERAGE_LIST,
            key=f"cov_{idx}"
        )

        rate = st.number_input(
            "Rate (%)",
            value=0.0,
            step=0.00001,
            format="%.5f",
            key=f"rate_{idx}"
        )

        tsi = st.text_input(
            "TSI IDR",
            value="",
            key=f"tsi_{idx}"
        )

        top_risk = st.text_input(
            "Top Risk (IDR)",
            value="",
            key=f"top_{idx}"
        )

    with col2:
        askrindo = st.number_input(
            "% Askrindo",
            value=10.0,
            step=0.01,
            key=f"ask_{idx}"
        )

        fakultatif = st.number_input(
            "% Fakultatif",
            value=0.0,
            step=0.01,
            key=f"fac_{idx}"
        )

        lol_pct = st.number_input(
            "LOL (%)",
            value=0.0,
            step=0.01,
            key=f"lol_{idx}"
        )

    with col3:
        lol_premi = st.number_input(
            "% LOL Premi",
            value=100.0,
            step=0.01,
            key=f"lolp_{idx}"
        )

        komisi_fak = st.number_input(
            "% Komisi Fakultatif",
            value=0.0,
            step=0.01,
            key=f"komf_{idx}"
        )

        akuisisi = st.number_input(
            "% Akuisisi",
            value=15.0,
            step=0.01,
            key=f"akq_{idx}"
        )

        st.button("🗑️ Hapus", on_click=remove_coverage, args=(i,))

    def to_float(x):
        try:
            return float(str(x).replace(",", ""))
        except:
            return 0.0

    inputs.append({
        "Coverage": coverage,
        "Rate": rate / 100,
        "TSI": to_float(tsi),
        "TopRisk": to_float(top_risk),
        "Askrindo": askrindo / 100,
        "Fakultatif": fakultatif / 100,
        "LOL": lol_pct / 100,
        "LOL_Premi": lol_premi / 100,
        "KomFak": komisi_fak / 100,
        "Akuisisi": akuisisi / 100
    })

st.button("➕ Tambah Coverage", on_click=add_coverage)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    rows = []

    for d in inputs:
        m = MASTER.loc[d["Coverage"]]

        # ===== Exposure Basis =====
        if d["LOL"] > 0:
            exposure = d["LOL"] * d["TSI"]
        elif d["TopRisk"] > 0:
            exposure = d["TopRisk"]
        else:
            exposure = d["TSI"]

        # ===== OR Cap =====
        tsi_ask = d["Askrindo"] * exposure
        exposure_or = min(tsi_ask, m["OR_Cap"])

        # ===== Pool =====
        pool_amt = min(
            m["%pool"] * exposure_or,
            m["Amount_Pool"] * d["Askrindo"]
        )

        fac_amt = d["Fakultatif"] * exposure_or
        or_amt = max(exposure_or - pool_amt - fac_amt, 0)

        # ===== Premium =====
        prem_100 = d["Rate"] * d["TSI"] * d["LOL_Premi"]

        prem_ask = prem_100 * d["Askrindo"]
        prem_pool = prem_100 * (pool_amt / exposure_or if exposure_or > 0 else 0)

        # ===== Commission =====
        acq = prem_ask * d["Akuisisi"]
        kom_pool = prem_pool * m["Komisi_Pool"]
        kom_fak = prem_100 * d["Fakultatif"] * d["KomFak"]

        # ===== EL =====
        if not pd.isna(m["Rate_Min"]):
            el_100 = m["Rate_Min"] * exposure * LOSS_RATIO
        else:
            el_100 = prem_100 * LOSS_RATIO

        el_ask = el_100 * d["Askrindo"]
        el_pool = el_100 * (pool_amt / exposure_or if exposure_or > 0 else 0)

        # ===== XOL =====
        prem_xol = XOL_RATE * or_amt

        expense = EXPENSE_RATIO * prem_ask

        result = (
            prem_ask
            - acq
            - prem_pool
            + kom_pool
            + kom_fak
            - el_ask
            + el_pool
            - prem_xol
            - expense
        )

        rows.append({
            "Coverage": d["Coverage"],
            "Prem_Askrindo": prem_ask,
            "Prem_OR": or_amt * d["Rate"],
            "Prem_POOL": prem_pool,
            "EL_Askrindo": el_ask,
            "EL_POOL": el_pool,
            "Prem_XOL": prem_xol,
            "Expense": expense,
            "Result": result,
            "%Result": result / prem_ask if prem_ask > 0 else 0
        })

    df = pd.DataFrame(rows)
    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df.style.format({
            c: "{:,.0f}" for c in df.columns if c not in ["Coverage", "%Result"]
        }).format({
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )
