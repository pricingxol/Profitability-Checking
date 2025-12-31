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
# LOAD MASTER EXCEL (SINGLE SOURCE OF TRUTH)
# =====================================================
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE)
df_master.columns = [c.strip().upper() for c in df_master.columns]

MASTER = df_master.set_index("COVERAGE")

# =====================================================
# ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi")

LOSS_RATIO = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE   = st.sidebar.number_input("Premi XOL (% dari Premi OR)", 0.0, 1.0, 0.14, 0.01)
EXP_RATIO  = st.sidebar.number_input("Expense Ratio", 0.0, 1.0, 0.15, 0.01)

# =====================================================
# INPUT COVERAGE
# =====================================================
if "rows" not in st.session_state:
    st.session_state.rows = [0]

def add_row():
    st.session_state.rows.append(len(st.session_state.rows))

def del_row(i):
    st.session_state.rows.pop(i)

st.subheader("📋 Input Coverage")

inputs = []

for i in st.session_state.rows:
    c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([2,1,2,1,1,1,1,1,0.5])

    with c1:
        cov = st.selectbox(
            "Coverage",
            MASTER.index.tolist(),
            key=f"cov_{i}"
        )

    m = MASTER.loc[cov]

    with c2:
        rate = st.number_input(
            "Rate (%)",
            value=round(float(m.get("RATE_MIN", 0)) * 100, 5),
            format="%.5f",
            key=f"rate_{i}"
        ) / 100

    with c3:
        tsi = st.number_input(
            "TSI IDR",
            value=0.0,
            format="%.0f",
            key=f"tsi_{i}"
        )

    with c4:
        ask = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}") / 100

    with c5:
        fac = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}") / 100

    with c6:
        kom_fak = st.number_input("% Komisi Fak", 0.0, 100.0, 0.0, key=f"komf_{i}") / 100

    with c7:
        lol = st.number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}") / 100

    with c8:
        acq = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"acq_{i}") / 100

    with c9:
        st.button("🗑️", on_click=del_row, args=(i,), key=f"del_{i}")

    inputs.append({
        "Coverage": cov,
        "Rate": rate,
        "TSI100": tsi,
        "ASK": ask,
        "FAC": fac,
        "KOM_FAK": kom_fak,
        "LOL": lol,
        "ACQ": acq
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CORE ENGINE
# =====================================================
def calc(row):
    m = MASTER.loc[row["Coverage"]]

    rate_min    = m.get("RATE_MIN", np.nan)
    OR_CAP      = m["OR_CAP"]
    pool_rate   = m["%POOL"]
    pool_cap    = m["AMOUNT_POOL"]
    kom_pool    = m["KOMISI_POOL"]

    TSI100 = row["TSI100"]

    TSI_Askrindo = row["ASK"] * TSI100

    TSI_Pool = min(
        pool_rate * TSI_Askrindo,
        pool_cap * row["ASK"] if not pd.isna(pool_cap) else 0
    )

    TSI_Fac = row["FAC"] * TSI100

    TSI_OR = TSI_Askrindo - TSI_Pool - TSI_Fac
    Exposure_OR = min(TSI_OR, OR_CAP)

    Prem100 = row["Rate"] * row["LOL"] * TSI100

    Prem_Askrindo = Prem100 * (TSI_Askrindo / TSI100) if TSI100 else 0
    Prem_POOL     = Prem100 * (TSI_Pool / TSI100) if TSI100 else 0
    Prem_Fac      = Prem100 * (TSI_Fac / TSI100) if TSI100 else 0
    Prem_OR       = Prem100 * (Exposure_OR / TSI100) if TSI100 else 0

    if not pd.isna(rate_min):
        EL100 = rate_min * LOSS_RATIO * (TSI100 * row["LOL"])
    else:
        EL100 = LOSS_RATIO * Prem100

    EL_Askrindo = EL100 * (TSI_Askrindo / TSI100) if TSI100 else 0
    EL_POOL     = EL100 * (TSI_Pool / TSI100) if TSI100 else 0
    EL_Fac      = EL100 * (TSI_Fac / TSI100) if TSI100 else 0

    Akuisisi = row["ACQ"] * Prem_Askrindo
    Kom_POOL = kom_pool * Prem_POOL
    Kom_Fac  = row["KOM_FAK"] * Prem_Fac

    Prem_XOL = XOL_RATE * Prem_OR
    Expense  = EXP_RATIO * Prem_Askrindo

    Result = (
        Prem_Askrindo
        - Akuisisi
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
        "Coverage": row["Coverage"],
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
if st.button("🚀 Calculate"):
    rows = [calc(r) for r in inputs]
    df = pd.DataFrame(rows)

    total = df.select_dtypes("number").sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"] if total["Prem_Askrindo"] else 0

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
