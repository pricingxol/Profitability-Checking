import streamlit as st
import pandas as pd
import numpy as np

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")
st.caption("Versi Excel-driven | Logic match Bulk Profitability")

# =============================
# LOAD MASTER EXCEL
# =============================
MASTER_FILE = "Master File.xlsx"

@st.cache_data
def load_master():
    xls = pd.ExcelFile(MASTER_FILE)
    df_all = []
    for s in xls.sheet_names:
        df = pd.read_excel(xls, s)
        df["Coverage"] = s
        df_all.append(df)
    return pd.concat(df_all, ignore_index=True)

df_master = load_master()

# =============================
# ASSUMSI
# =============================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01)
PREMI_XOL  = st.sidebar.number_input("Asumsi Premi XOL", 0.0, 1.0, 0.1407, 0.0001)
EXP_RATIO  = st.sidebar.number_input("Asumsi Expense", 0.0, 1.0, 0.15, 0.01)

# =============================
# INPUT COVERAGE
# =============================
st.subheader("📋 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = [{}]

def add_row():
    st.session_state.rows.append({})

def delete_row(i):
    st.session_state.rows.pop(i)

results = []

for i, row in enumerate(st.session_state.rows):

    cols = st.columns([2,1,2,1,1,1,1,1,0.3])

    with cols[0]:
        coverage = st.selectbox(
            "Coverage",
            df_master["Coverage"].unique(),
            key=f"cov_{i}"
        )

    with cols[1]:
        rate = st.number_input("Rate (%)", 0.0, 100.0, 0.0, format="%.5f", key=f"rate_{i}") / 100

    with cols[2]:
        tsi = st.text_input("TSI IDR", key=f"tsi_{i}")
        tsi = float(tsi) if tsi not in ["", None] else 0.0

    with cols[3]:
        ask = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}") / 100

    with cols[4]:
        fac = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}") / 100

    with cols[5]:
        kom_fac = st.number_input("% Komisi Fak", 0.0, 100.0, 0.0, key=f"komfac_{i}") / 100

    with cols[6]:
        lol = st.number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}") / 100

    with cols[7]:
        acq = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"acq_{i}") / 100

    with cols[8]:
        st.button("🗑", on_click=delete_row, args=(i,), key=f"del_{i}")

    # =============================
    # MASTER LOOKUP
    # =============================
    m = df_master[df_master["Coverage"] == coverage].iloc[0]

    OR_CAP     = m["OR_CAP"]
    POOL_RATE  = m["POOL_RATE"]
    POOL_CAP   = m["POOL_CAP"]
    KOM_POOL   = m["KOMISI_POOL"]
    RATE_MIN   = m["RATE_MIN"]

    # =============================
    # TSI LOGIC
    # =============================
    TSI100 = tsi
    TSI_Askrindo = ask * TSI100
    Exposure_OR  = min(TSI_Askrindo, OR_CAP)

    TSI_POOL = min(POOL_RATE * TSI_Askrindo, POOL_CAP * ask)
    TSI_FAC  = fac * TSI100
    TSI_OR   = TSI_Askrindo - TSI_POOL - TSI_FAC

    # =============================
    # PREMIUM
    # =============================
    Prem100 = rate * lol * TSI100
    Prem_Askrindo = Prem100 * ask
    Prem_POOL = Prem100 * (TSI_POOL / TSI100 if TSI100 > 0 else 0)
    Prem_FAC  = Prem100 * fac
    Prem_OR   = Prem100 * (TSI_OR / TSI100 if TSI100 > 0 else 0)

    # =============================
    # LOSS
    # =============================
    if not pd.isna(RATE_MIN):
        EL100 = RATE_MIN * LOSS_RATIO * (lol * TSI100)
    else:
        EL100 = LOSS_RATIO * Prem100

    EL_Askrindo = EL100 * ask
    EL_POOL = EL100 * (TSI_POOL / TSI100 if TSI100 > 0 else 0)
    EL_FAC  = EL100 * fac

    # =============================
    # COST
    # =============================
    Akuisisi = acq * Prem_Askrindo
    Prem_XOL = PREMI_XOL * Prem_OR
    Expense  = EXP_RATIO * Prem_Askrindo

    Kom_POOL = KOM_POOL * Prem_POOL
    Kom_FAC  = kom_fac * Prem_FAC

    # =============================
    # RESULT
    # =============================
    Result = (
        Prem_Askrindo
        - Akuisisi
        - Prem_POOL
        - Prem_FAC
        + Kom_POOL
        + Kom_FAC
        - EL_Askrindo
        + EL_POOL
        + EL_FAC
        - Prem_XOL
        - Expense
    )

    results.append({
        "Coverage": coverage,
        "Prem_Askrindo": Prem_Askrindo,
        "Prem_OR": Prem_OR,
        "Prem_POOL": Prem_POOL,
        "EL_Askrindo": EL_Askrindo,
        "EL_POOL": EL_POOL,
        "Prem_XOL": Prem_XOL,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo != 0 else 0
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =============================
# OUTPUT
# =============================
if results:
    df = pd.DataFrame(results)
    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]
    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.subheader("📈 Hasil Profitability")

    fmt = {}
    for c in df.columns:
        if c == "%Result":
            fmt[c] = "{:.2%}"
        elif c != "Coverage":
            fmt[c] = "{:,.0f}"

    st.dataframe(df.style.format(fmt), use_container_width=True)
