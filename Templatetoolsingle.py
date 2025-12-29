import streamlit as st
import pandas as pd
import numpy as np

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

MASTER_FILE = "Master File.xlsx"

# =========================
# LOAD MASTER
# =========================
df_master = pd.read_excel(MASTER_FILE)

df_master.columns = [c.strip() for c in df_master.columns]

MASTER = df_master.set_index("Coverage").to_dict(orient="index")
COVERAGE_LIST = list(MASTER.keys())

# =========================
# SIDEBAR ASSUMPTION
# =========================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE   = st.sidebar.number_input("Premi XOL (%)", 0.0, 100.0, 14.07) / 100
EXP_RATIO  = st.sidebar.number_input("Expense (%)", 0.0, 100.0, 15.00) / 100

# =========================
# HEADER
# =========================
st.title("📊 Profitability Checking – Akseptasi Manual")
st.caption("Versi Excel-driven | Logic match Bulk Profitability")

# =========================
# INPUT ROWS (STATEFUL)
# =========================
if "rows" not in st.session_state:
    st.session_state.rows = [0]

def add_row():
    st.session_state.rows.append(len(st.session_state.rows))

def delete_row(i):
    st.session_state.rows.pop(i)

rows_data = []

st.subheader("📋 Input Coverage")

for i in st.session_state.rows:
    with st.container():
        cols = st.columns([2,1,2,1,1,1,1,1,0.3])

        cov = cols[0].selectbox("Coverage", COVERAGE_LIST, key=f"cov_{i}")
        rate = cols[1].number_input("Rate (%)", value=0.00000, format="%.5f", key=f"rate_{i}") / 100
        tsi  = cols[2].number_input("TSI IDR", value=0.0, format="%.0f", step=None, key=f"tsi_{i}")
        ask  = cols[3].number_input("% Askrindo", value=10.0, key=f"ask_{i}") / 100
        fac  = cols[4].number_input("% Fakultatif", value=0.0, key=f"fac_{i}") / 100
        komf = cols[5].number_input("% Komisi Fak", value=0.0, key=f"komf_{i}") / 100
        lol  = cols[6].number_input("% LOL", value=100.0, key=f"lol_{i}") / 100
        acq  = cols[7].number_input("% Akuisisi", value=15.0, key=f"acq_{i}") / 100

        if cols[8].button("🗑️", key=f"del_{i}"):
            delete_row(i)
            st.rerun()

        rows_data.append([cov, rate, tsi, ask, fac, komf, lol, acq])

st.button("➕ Tambah Coverage", on_click=add_row)

# =========================
# CALCULATION
# =========================
if st.button("🚀 Calculate"):
    result_rows = []

    for r in rows_data:
        cov, rate, TSI100, ask, fac, komf, lol, acq = r
        m = MASTER[cov]

        OR_CAP   = m["OR_Cap"]
        pool_rt  = m["%pool"]
        pool_cap = m["Amount_Pool"]
        kom_pool = m["Komisi_Pool"]
        rate_min = m["Rate_Min"]

        TSI_Askrindo = ask * TSI100
        TSI_Pool = min(pool_rt * TSI_Askrindo, pool_cap * ask)
        TSI_Fac  = fac * TSI100
        TSI_OR   = max(TSI_Askrindo - TSI_Pool - TSI_Fac, 0)

        Exposure_OR = min(TSI_Askrindo, OR_CAP)

        Prem100 = rate * lol * TSI100

        Prem_Askrindo = Prem100 * ask
        Prem_POOL = Prem100 * (TSI_Pool / TSI100 if TSI100 else 0)
        Prem_Fac  = Prem100 * fac
        Prem_OR   = Prem100 * (TSI_OR / TSI100 if TSI100 else 0)

        Acq_amt = acq * Prem_Askrindo

        Kom_POOL = kom_pool * Prem_POOL
        Kom_Fac  = komf * Prem_Fac

        if not pd.isna(rate_min):
            EL100 = rate_min * LOSS_RATIO * TSI100
        else:
            EL100 = LOSS_RATIO * Prem100

        EL_Askrindo = EL100 * ask
        EL_POOL = EL100 * (TSI_Pool / TSI100 if TSI100 else 0)
        EL_Fac  = EL100 * fac

        Prem_XOL = XOL_RATE * Prem_OR
        Expense  = EXP_RATIO * Prem_Askrindo

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

        result_rows.append([
            cov, Prem_Askrindo, Prem_OR, Prem_POOL,
            EL_Askrindo, EL_POOL,
            Prem_XOL, Expense, Result,
            Result / Prem_Askrindo if Prem_Askrindo else 0
        ])

    df = pd.DataFrame(result_rows, columns=[
        "Coverage","Prem_Askrindo","Prem_OR","Prem_POOL",
        "EL_Askrindo","EL_POOL",
        "Prem_XOL","Expense","Result","%Result"
    ])

    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, total.to_frame().T], ignore_index=True)

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
