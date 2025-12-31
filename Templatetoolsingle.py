import os
import streamlit as st
import pandas as pd
import numpy as np

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Actuary Profitability Model by Divisi Aktuaria",
    layout="wide",
)

BASE_DIR = os.path.dirname(__file__)
MASTER_FILE = os.path.join(BASE_DIR, "Master File.xlsx")
MASTER_SHEET = "master coverage"

# =========================
# LOAD MASTER
# =========================
df_master = pd.read_excel(
    MASTER_FILE,
    sheet_name=MASTER_SHEET
)

df_master.columns = df_master.columns.str.strip()
coverage_list = df_master["Coverage"].dropna().tolist()

# DEBUG (hapus nanti)
st.write("Master sheet loaded:")
st.dataframe(df_master.head())


# =========================
# UI
# =========================
st.title("📋 Actuary Profitability Model")

if "rows" not in st.session_state:
    st.session_state.rows = [0]

def add_row():
    st.session_state.rows.append(len(st.session_state.rows))

def remove_row(i):
    st.session_state.rows.pop(i)

rows_data = []

st.header("Input Coverage")

for i in st.session_state.rows:
    with st.container():
        st.subheader(f"Coverage #{i+1}")

        col1, col2, col3 = st.columns(3)

        with col1:
            coverage = st.selectbox("Coverage", coverage_list, key=f"cov_{i}")
            rate = st.number_input("Rate (%)", format="%.5f", key=f"rate_{i}")
            tsi = st.text_input("TSI IDR", key=f"tsi_{i}")

        with col2:
            ask_share = st.number_input("% Askrindo", value=10.0, step=0.01, key=f"ask_{i}") / 100
            fak_share = st.number_input("% Fakultatif", value=0.0, step=0.01, key=f"fak_{i}") / 100
            lol = st.number_input("% LOL", value=100.0, format="%.5f", key=f"lol_{i}") / 100

        with col3:
            kom_fak = st.number_input("% Komisi Fakultatif", value=0.0, step=0.01, key=f"komfak_{i}") / 100
            akuisisi = st.number_input("% Akuisisi", value=15.0, step=0.01, key=f"aku_{i}") / 100
            top_risk = st.text_input("Top Risk (IDR)", key=f"top_{i}")

        if st.button("🗑 Hapus", key=f"del_{i}"):
            remove_row(i)
            st.experimental_rerun()

        rows_data.append({
            "coverage": coverage,
            "rate": rate / 100,
            "tsi": float(tsi) if tsi else 0.0,
            "ask_share": ask_share,
            "fak_share": fak_share,
            "kom_fak": kom_fak,
            "aku": akuisisi,
            "lol": lol,
            "top_risk": float(top_risk) if top_risk else float(tsi) if tsi else 0.0
        })

st.button("➕ Tambah Coverage", on_click=add_row)

# =========================
# CALCULATION
# =========================
if st.button("🚀 Calculate"):
    results = []

    for r in rows_data:
        m = get_master_row(r["coverage"])

        OR_CAP = m["OR_Cap"]
        POOL_RATE = m["%pool"]
        POOL_CAP = m["Amount_Pool"]
        KOM_POOL = m["Komisi_Pool"]
        RATE_MIN = m["Rate_Min"] if not pd.isna(m["Rate_Min"]) else None

        TSI = r["tsi"]
        TOP = r["top_risk"]
        LOL = r["lol"]

        exposure = min(TSI, TOP) * LOL if LOL > 0 else TSI
        exposure_ask = exposure * r["ask_share"]

        prem_100 = r["rate"] * TSI
        prem_eff = prem_100 * LOL
        prem_ask = prem_eff * r["ask_share"]

        exposure_or = min(exposure_ask, OR_CAP)
        prem_or = prem_eff * (exposure_or / exposure_ask) if exposure_ask > 0 else 0

        exposure_pool = min(POOL_RATE * exposure_ask, POOL_CAP * r["ask_share"])
        prem_pool = prem_eff * (exposure_pool / exposure_ask) if exposure_ask > 0 else 0

        if RATE_MIN:
            el_100 = RATE_MIN * exposure
        else:
            el_100 = prem_eff * 0.4  # default LR fallback

        el_ask = el_100 * r["ask_share"]
        el_pool = el_100 * (exposure_pool / exposure) if exposure > 0 else 0

        kom_pool = prem_pool * KOM_POOL
        kom_fak = prem_eff * r["fak_share"] * r["kom_fak"]
        akuisisi = prem_ask * r["aku"]

        result = (
            prem_ask
            - akuisisi
            - prem_pool
            + kom_pool
            + kom_fak
            - el_ask
            + el_pool
        )

        results.append({
            "Coverage": r["coverage"],
            "Prem_Askrindo": prem_ask,
            "Prem_OR": prem_or,
            "Prem_POOL": prem_pool,
            "EL_Askrindo": el_ask,
            "EL_POOL": el_pool,
            "Result": result,
            "%Result": result / prem_ask if prem_ask > 0 else 0
        })

    df = pd.DataFrame(results)
    total = df.sum(numeric_only=True)
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"] if total["Prem_Askrindo"] > 0 else 0

    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    st.header("📊 Hasil Profitability")
    st.dataframe(df.style.format({
        "%Result": "{:.2%}"
    }))
