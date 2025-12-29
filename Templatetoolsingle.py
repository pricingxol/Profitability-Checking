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
MASTER_FILE = "master_coverage.xlsx"
df_master = pd.read_excel(MASTER_FILE, sheet_name="MASTER")

MASTER = df_master.set_index("Coverage").to_dict(orient="index")
COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE   = st.sidebar.number_input("Premi XOL (%)", 0.0, 100.0, 14.07, 0.01) / 100
EXP_RATE   = st.sidebar.number_input("Expense (%)", 0.0, 100.0, 15.00, 0.01) / 100

# =====================================================
# POLICY INFO
# =====================================================
st.subheader("📄 Informasi Polis")

c1, c2, c3 = st.columns(3)
insured = c1.text_input("Nama Tertanggung", "")
start   = c2.date_input("Periode Mulai")
end     = c3.date_input("Periode Akhir")

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

rows = []

for i in range(len(st.session_state.rows)):
    with st.container():
        cols = st.columns([2,1,2,1,1,1,1,1,0.3])

        cov = cols[0].selectbox(
            "Coverage", COVERAGE_LIST, key=f"cov_{i}"
        )

        rate = cols[1].number_input(
            "Rate (%)", 0.0, 100.0, 0.0,
            format="%.5f", key=f"rate_{i}"
        ) / 100

        tsi_text = cols[2].text_input(
            "TSI IDR", key=f"tsi_{i}"
        )

        ask = cols[3].number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}") / 100
        fac = cols[4].number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}") / 100
        kom_fac = cols[5].number_input("% Komisi Fak", 0.0, 100.0, 0.0, key=f"kom_{i}") / 100
        lol = cols[6].number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}") / 100
        acq = cols[7].number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"acq_{i}") / 100

        if cols[8].button("🗑", key=f"del_{i}"):
            delete_row(i)
            st.experimental_rerun()

        try:
            tsi = float(tsi_text.replace(",", ""))
        except:
            tsi = 0

        rows.append({
            "Coverage": cov,
            "Rate": rate,
            "TSI": tsi,
            "Ask": ask,
            "Fac": fac,
            "KomFac": kom_fac,
            "LOL": lol,
            "Acq": acq
        })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):
    results = []

    for r in rows:
        m = MASTER[r["Coverage"]]

        TSI100 = r["TSI"]
        TSI_Askrindo = r["Ask"] * TSI100
        TSI_Pool = min(
            m["Pool_Rate"] * TSI_Askrindo,
            m["Pool_Cap"] * r["Ask"]
        )
        TSI_Fac = r["Fac"] * TSI100
        TSI_OR = max(TSI_Askrindo - TSI_Pool - TSI_Fac, 0)

        Prem100 = r["Rate"] * r["LOL"] * TSI100

        Prem_Askrindo = Prem100 * (TSI_Askrindo / TSI100)
        Prem_POOL = Prem100 * (TSI_Pool / TSI100)
        Prem_Fac = Prem100 * (TSI_Fac / TSI100)
        Prem_OR = Prem100 * (TSI_OR / TSI100)

        Prem_XOL = XOL_RATE * Prem_OR
        Expense = EXP_RATE * Prem_Askrindo
        Acq = r["Acq"] * Prem_Askrindo

        EL100 = m["Rate_Min"] * LOSS_RATIO * TSI100
        EL_Askrindo = EL100 * (TSI_Askrindo / TSI100)
        EL_POOL = EL100 * (TSI_Pool / TSI100)
        EL_Fac = EL100 * (TSI_Fac / TSI100)

        Result = (
            Prem_Askrindo
            - Prem_POOL - Prem_Fac
            - Acq
            + m["Komisi_Pool"] * Prem_POOL
            + r["KomFac"] * Prem_Fac
            - EL_Askrindo
            + EL_POOL + EL_Fac
            - Prem_XOL
            - Expense
        )

        results.append([
            r["Coverage"],
            Prem_Askrindo,
            Prem_OR,
            Prem_POOL,
            EL_Askrindo,
            EL_POOL,
            Prem_XOL,
            Expense,
            Result,
            Result / Prem_Askrindo if Prem_Askrindo else 0
        ])

    df = pd.DataFrame(results, columns=[
        "Coverage","Prem_Askrindo","Prem_OR","Prem_POOL",
        "EL_Askrindo","EL_POOL","Prem_XOL","Expense",
        "Result","%Result"
    ])

    total = df.sum(numeric_only=True)
    total["Coverage"] = "TOTAL"
    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.subheader("📊 Hasil Profitability")
    st.dataframe(
        df.style.format({
            "Prem_Askrindo":"{:,.0f}",
            "Prem_OR":"{:,.0f}",
            "Prem_POOL":"{:,.0f}",
            "EL_Askrindo":"{:,.0f}",
            "EL_POOL":"{:,.0f}",
            "Prem_XOL":"{:,.0f}",
            "Expense":"{:,.0f}",
            "Result":"{:,.0f}",
            "%Result":"{:.2%}"
        }),
        use_container_width=True
    )
