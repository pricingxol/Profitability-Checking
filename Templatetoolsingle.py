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
# LOAD MASTER EXCEL
# =====================================================
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE)
df_master.columns = df_master.columns.str.strip()

coverage_list = df_master["Coverage"].tolist()

MASTER = df_master.set_index("Coverage").to_dict(orient="index")

# =====================================================
# SIDEBAR – ASSUMPTIONS
# =====================================================
st.sidebar.header("📊 Asumsi Profitability")

loss_ratio = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    min_value=0.0,
    max_value=1.0,
    value=0.40,
    format="%.5f"
)

xol_rate = st.sidebar.number_input(
    "Asumsi Premi XOL",
    min_value=0.0,
    max_value=1.0,
    value=0.14070,
    format="%.5f"
)

expense_ratio = st.sidebar.number_input(
    "Asumsi Expense",
    min_value=0.0,
    max_value=1.0,
    value=0.15,
    format="%.5f"
)

# =====================================================
# POLICY INFO
# =====================================================
st.markdown("### 📄 Informasi Polis")

colA, colB, colC = st.columns(3)

with colA:
    insured = st.text_input("Nama Tertanggung", value="")

with colB:
    start_date = st.date_input("Periode Mulai")

with colC:
    end_date = st.date_input("Periode Akhir")

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

for i, _ in enumerate(st.session_state.rows):

    st.markdown(f"#### Coverage #{i+1}")

    c1, c2, c3, c4 = st.columns([2,2,2,1])

    with c1:
        cov = st.selectbox("Coverage", coverage_list, key=f"cov_{i}")

        rate = st.number_input(
            "Rate (%)",
            format="%.5f",
            key=f"rate_{i}"
        )

        tsi_raw = st.text_input(
            "TSI IDR",
            key=f"tsi_{i}",
            help="Input angka penuh tanpa koma"
        )

        try:
            tsi = float(tsi_raw)
        except:
            tsi = 0.0

    with c2:
        askrindo = st.number_input("% Askrindo", 0.0, 100.0, 10.0, key=f"ask_{i}")
        fakultatif = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}")
        lol = st.number_input("% LOL", 0.0, 100.0, 100.0, key=f"lol_{i}")

    with c3:
        komisi_fak = st.number_input("% Komisi Fakultatif", 0.0, 100.0, 0.0, key=f"kf_{i}")
        akuisisi = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"ak_{i}")

    with c4:
        st.write("")
        if st.button("🗑️", key=f"del_{i}"):
            delete_row(i)
            st.experimental_rerun()

    st.session_state.rows[i] = {
        "Coverage": cov,
        "Rate": rate / 100,
        "TSI": tsi,
        "Askrindo": askrindo / 100,
        "Fakultatif": fakultatif / 100,
        "LOL": lol / 100,
        "Komisi_Fak": komisi_fak / 100,
        "Akuisisi": akuisisi / 100
    }

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    results = []

    for r in st.session_state.rows:

        m = MASTER[r["Coverage"]]

        rate_min = m.get("Rate_Min")
        or_cap = m.get("OR_Cap")
        pool_rate = m.get("%pool", 0)
        pool_cap = m.get("Amount_Pool", 0)
        komisi_pool = m.get("Komisi_Pool", 0)

        TSI100 = r["TSI"]
        TSI_Askrindo = r["Askrindo"] * TSI100

        Exposure_OR = min(TSI_Askrindo, or_cap)

        TSI_Pool = min(pool_rate * TSI_Askrindo, pool_cap * r["Askrindo"])
        TSI_Fac = r["Fakultatif"] * TSI100
        TSI_OR = max(TSI_Askrindo - TSI_Pool - TSI_Fac, 0)

        Premi100 = r["Rate"] * r["LOL"] * TSI100

        Prem_Askrindo = Premi100 * r["Askrindo"]
        Prem_POOL = Premi100 * (TSI_Pool / TSI100) if TSI100 > 0 else 0
        Prem_OR = Premi100 * (TSI_OR / TSI100) if TSI100 > 0 else 0

        # ===== EL =====
        if pd.isna(rate_min):
            EL100 = loss_ratio * Premi100
        else:
            EL100 = rate_min * loss_ratio * TSI100 * r["LOL"]

        EL_Askrindo = EL100 * r["Askrindo"]
        EL_POOL = EL100 * (TSI_Pool / TSI100) if TSI100 > 0 else 0

        Prem_XOL = xol_rate * Prem_OR
        Expense = expense_ratio * Prem_Askrindo

        Result = (
            Prem_Askrindo
            - Prem_POOL
            - Prem_XOL
            - (r["Akuisisi"] * Prem_Askrindo)
            + (komisi_pool * Prem_POOL)
            + (r["Komisi_Fak"] * Prem_POOL)
            - EL_Askrindo
            + EL_POOL
            - Expense
        )

        results.append({
            "Coverage": r["Coverage"],
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

    df = pd.DataFrame(results)

    total = df.select_dtypes(np.number).sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"] if total["Prem_Askrindo"] != 0 else 0

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.markdown("### 📈 Hasil Profitability")

    st.dataframe(
        df.style
        .format("{:,.0f}", subset=[
            "Prem_Askrindo","Prem_OR","Prem_POOL",
            "EL_Askrindo","EL_POOL","Prem_XOL",
            "Expense","Result"
        ])
        .format("{:.2%}", subset=["%Result"]),
        use_container_width=True
    )
