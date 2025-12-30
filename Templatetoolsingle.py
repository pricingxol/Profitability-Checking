import streamlit as st
import pandas as pd

# =========================
# CONFIG
# =========================
MASTER_FILE = "Master File.xlsx"
MASTER_SHEET = "master coverage"

st.set_page_config(
    page_title="Actuary Profitability Model",
    layout="wide"
)

st.title("📊 Actuary Profitability Model")

# =========================
# LOAD MASTER
# =========================
df_master = pd.read_excel(MASTER_FILE, sheet_name=MASTER_SHEET)

df_master.columns = df_master.columns.str.strip()

# =========================
# HELPERS
# =========================
def parse_number(x):
    try:
        return float(str(x).replace(",", "").strip())
    except:
        return 0.0

# =========================
# SESSION
# =========================
if "rows" not in st.session_state:
    st.session_state.rows = [{}]

# =========================
# INPUT UI
# =========================
st.header("📋 Input Coverage")

for i, r in enumerate(st.session_state.rows):
    st.subheader(f"Coverage #{i+1}")
    c1, c2, c3 = st.columns(3)

    with c1:
        coverage = st.selectbox(
            "Coverage",
            df_master["Coverage"].tolist(),
            key=f"cov_{i}"
        )

        rate = st.number_input(
            "Rate (%)",
            value=0.00000,
            format="%.5f",
            key=f"rate_{i}"
        )

        tsi = st.text_input(
            "TSI IDR",
            value="",
            key=f"tsi_{i}"
        )

    with c2:
        ask_share = st.number_input(
            "% Askrindo",
            value=10.00,
            format="%.2f",
            key=f"ask_{i}"
        )

        fac_share = st.number_input(
            "% Fakultatif",
            value=0.00,
            format="%.2f",
            key=f"fac_{i}"
        )

        lol_pct = st.number_input(
            "% LOL",
            value=100.00,
            format="%.2f",
            key=f"lol_{i}"
        )

    with c3:
        komisi_fac = st.number_input(
            "% Komisi Fakultatif",
            value=0.00,
            format="%.2f",
            key=f"komfac_{i}"
        )

        akuisisi = st.number_input(
            "% Akuisisi",
            value=15.00,
            format="%.2f",
            key=f"aku_{i}"
        )

        top_risk = st.text_input(
            "Top Risk (IDR) – default = TSI",
            value=tsi,
            key=f"top_{i}"
        )

# =========================
# CALCULATION
# =========================
if st.button("🚀 Calculate"):
    results = []

    for i, r in enumerate(st.session_state.rows):
        m = df_master[df_master["Coverage"] == st.session_state[f"cov_{i}"]].iloc[0]

        TSI100 = parse_number(st.session_state[f"tsi_{i}"])
        TopRisk = parse_number(st.session_state[f"top_{i}"])
        Rate = st.session_state[f"rate_{i}"] / 100
        LOL = st.session_state[f"lol_{i}"] / 100

        ask = st.session_state[f"ask_{i}"] / 100
        fac = st.session_state[f"fac_{i}"] / 100

        # Exposure
        Exposure = TopRisk * LOL if LOL > 0 else TSI100

        # Master params
        OR_CAP = parse_number(m["OR_Cap"])
        POOL_RATE = parse_number(m["%pool"])
        POOL_CAP = parse_number(m["Amount_Pool"])
        KOM_POOL = parse_number(m["Komisi_Pool"])

        # TSI split
        TSI_Askrindo = ask * Exposure

        TSI_POOL = min(
            POOL_RATE * TSI_Askrindo,
            POOL_CAP * ask
        )

        TSI_Fac = fac * Exposure
        TSI_OR = TSI_Askrindo - TSI_POOL - TSI_Fac

        # Premi
        Prem_100 = Rate * Exposure
        Prem_Askrindo = Prem_100 * ask
        Prem_POOL = Prem_100 * (TSI_POOL / Exposure) if Exposure > 0 else 0
        Prem_OR = Prem_100 * (TSI_OR / Exposure) if Exposure > 0 else 0

        # Klaim
        Loss_Ratio = 0.4
        Rate_Min = parse_number(m["Rate_Min"])

        if Rate_Min > 0:
            EL_100 = Rate_Min * Loss_Ratio * Exposure
        else:
            EL_100 = Loss_Ratio * Prem_100

        EL_Askrindo = EL_100 * ask
        EL_POOL = EL_100 * (TSI_POOL / Exposure) if Exposure > 0 else 0

        # Biaya
        Akuisisi = Prem_Askrindo * (st.session_state[f"aku_{i}"] / 100)
        Prem_XOL = Prem_OR * 0.14
        Expense = Akuisisi

        Result = (
            Prem_Askrindo
            - Akuisisi
            - Prem_POOL
            + (Prem_POOL * KOM_POOL)
            - EL_Askrindo
            + EL_POOL
            - Prem_XOL
            - Expense
        )

        results.append({
            "Coverage": m["Coverage"],
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
    total = df.sum(numeric_only=True)
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    st.header("📈 Hasil Profitability")
    st.dataframe(pd.concat([df, pd.DataFrame([total])], ignore_index=True))
