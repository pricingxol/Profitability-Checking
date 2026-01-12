import streamlit as st
import pandas as pd
import numpy as np
import io

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Asuransi Umum",
    layout="wide"
)

st.title("📊 Profitability Checking – Asuransi Umum")
st.caption("by Divisi Aktuaria Askrindo")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE)
df_master.columns = [c.strip().upper() for c in df_master.columns]
MASTER = df_master.set_index("COVERAGE")

# =====================================================
# ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi")

LOSS_RATIO = st.sidebar.number_input(
    "Asumsi Loss Ratio", 0.0, 1.0, 0.50000,
    step=0.00001, format="%.5f"
)

XOL_RATE = st.sidebar.number_input(
    "Premi XOL (% dari Premi OR)", 0.0, 1.0, 0.14000,
    step=0.00001, format="%.5f"
)

EXP_RATIO = st.sidebar.number_input(
    "Expense Ratio", 0.0, 1.0, 0.15000,
    step=0.00001, format="%.5f"
)

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

    st.markdown("**Coverage**")
    cov = st.selectbox("", MASTER.index.tolist(), key=f"cov_{i}")
    m = MASTER.loc[cov]

    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns(
        [1.5, 2, 1, 1, 1, 1, 1, 1, 1.2, 0.5]
    )

    with c1:
        rate_raw = st.text_input("Rate (%)", "", key=f"rate_{i}")
        rate = float(rate_raw.replace(",", ".")) / 100 if rate_raw else 0.0

    with c2:
        tsi_raw = st.text_input("TSI IDR", "0", key=f"tsi_{i}")
        tsi = float(tsi_raw.replace(",", "")) if tsi_raw else 0.0

    with c3:
        ask = st.number_input("% Askrindo", 0.0, 100.0, 100.0, key=f"ask_{i}") / 100

    with c4:
        fac = st.number_input("% Fakultatif", 0.0, 100.0, 0.0, key=f"fac_{i}") / 100

    with c5:
        acq = st.number_input("% Akuisisi", 0.0, 100.0, 15.0, key=f"acq_{i}") / 100

    with c6:
        kom_fak = st.number_input("% Komisi Fak", 0.0, 100.0, 0.0, key=f"komf_{i}") / 100

    with c7:
        lol_exp = st.number_input("% LOL Exposure", 0.0, 100.0, 100.0, key=f"lol_exp_{i}") / 100

    with c8:
        lol_prem = st.number_input("% LOL Premi", 0.0, 100.0, 100.0, key=f"lol_prem_{i}") / 100

    with c9:
        top_raw = st.text_input("Top Risk IDR", "", key=f"top_{i}")
        top_risk = float(top_raw.replace(",", "")) if top_raw else tsi

    with c10:
        st.button("🗑️", on_click=del_row, args=(i,), key=f"del_{i}")

    inputs.append({
        "Coverage": cov,
        "Rate": rate,
        "TSI": tsi,
        "TOP_RISK": top_risk,
        "ASK": ask,
        "FAC": fac,
        "ACQ": acq,
        "KOM_FAK": kom_fak,
        "LOL_EXP": lol_exp,
        "LOL_PREM": lol_prem
    })

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CORE ENGINE
# =====================================================
def calc(row):
    m = MASTER.loc[row["Coverage"]]

    rate_min  = m.get("RATE_MIN", np.nan)
    OR_CAP    = m["OR_CAP"]
    pool_rate = m["%POOL"]
    pool_cap  = m["AMOUNT_POOL"]
    kom_pool  = m["KOMISI_POOL"]

    TSI100 = min(row["TSI"], row["TOP_RISK"])
    TSI_Askrindo = row["ASK"] * TSI100

    TSI_Pool = min(pool_rate * TSI_Askrindo, pool_cap * row["ASK"])
    TSI_Fac  = row["FAC"] * TSI100

    TSI_OR = max(TSI_Askrindo - TSI_Pool - TSI_Fac, 0)
    Exposure_OR = min(TSI_OR, OR_CAP)

    Prem100 = row["Rate"] * row["LOL_PREM"] * TSI100

    Prem_Askrindo = Prem100 * (TSI_Askrindo / TSI100) if TSI100 else 0
    Prem_POOL     = Prem100 * (TSI_Pool / TSI100) if TSI100 else 0
    Prem_Fac      = Prem100 * (TSI_Fac / TSI100) if TSI100 else 0
    Prem_OR       = Prem100 * (Exposure_OR / TSI100) if TSI100 else 0

    # ===============================
    # EXPECTED LOSS (LOCKED LOGIC)
    # ===============================
    EL100 = (
        rate_min * LOSS_RATIO * (TSI100 * row["LOL_EXP"])
        if not pd.isna(rate_min)
        else LOSS_RATIO * Prem100
    )

    EL_Askrindo = EL100 * (TSI_Askrindo / TSI100) if TSI100 else 0
    EL_POOL     = EL100 * (TSI_Pool / TSI100) if TSI100 else 0
    EL_Fac      = EL100 * (TSI_Fac / TSI100) if TSI100 else 0
    EL_OR       = EL100 * (Exposure_OR / TSI100) if TSI100 else 0

    # ===============================
    # SHORTFALL (INFORMATIONAL)
    # ===============================
    Prem_Shortfall = Prem_Askrindo - Prem_POOL - Prem_Fac - Prem_OR
    EL_Shortfall   = EL_Askrindo - EL_POOL - EL_Fac - EL_OR

    Akuisisi = row["ACQ"] * Prem_Askrindo
    Kom_POOL = kom_pool * Prem_POOL
    Kom_Fac  = row["KOM_FAK"] * Prem_Fac

    Prem_XOL = XOL_RATE * Prem_OR
    Expense  = EXP_RATIO * Prem_Askrindo

    # ===============================
    # FINAL RESULT (LOCKED)
    # ===============================
    Result = (
        Prem_Askrindo
        - Akuisisi
        - Prem_POOL
        + Kom_POOL
        - Prem_Fac
        + Kom_Fac
        - EL_Askrindo
        + EL_POOL
        + EL_Fac
        - Expense
        - Prem_XOL
    )


    return {
        "Coverage": row["Coverage"],
        "Prem_Askrindo": Prem_Askrindo,
        "Prem_OR": Prem_OR,
        "Prem_POOL": Prem_POOL,
        "Prem_Fakultatif": Prem_Fac,
        "Prem_Shortfall": Prem_Shortfall,
        "EL_Askrindo": EL_Askrindo,
        "EL_OR": EL_OR,
        "EL_POOL": EL_POOL,
        "EL_Fakultatif": EL_Fac,
        "EL_Shortfall": EL_Shortfall,
        "Prem_XOL": Prem_XOL,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
    }

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    df = pd.DataFrame([calc(r) for r in inputs])

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
            "Prem_Fakultatif": "{:,.0f}",
            "Prem_Shortfall": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "EL_OR": "{:,.0f}",
            "EL_POOL": "{:,.0f}",
            "EL_Fakultatif": "{:,.0f}",
            "EL_Shortfall": "{:,.0f}",
            "Prem_XOL": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )

    sf_cov = df.loc[df["Prem_Shortfall"] > 0, "Coverage"].tolist()
    if sf_cov:
        st.warning(
            "⚠️ Terdapat shortfall pada coverage: "
            + ", ".join(sf_cov)
            + ". Shortfall telah tercermin dalam premi dan hasil profitabilitas sebagai bagian dari risiko net Askrindo."
        )
