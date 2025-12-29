import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from datetime import datetime

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
MASTER_FILE = "Master File.xlsx"
df_master = pd.read_excel(MASTER_FILE, sheet_name="master coverage")
df_master["Coverage"] = df_master["Coverage"].str.strip()

MASTER = df_master.set_index("Coverage").to_dict("index")
COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# SIDEBAR – ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Profitability")

loss_ratio = st.sidebar.number_input(
    "Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01
)

premi_xol_pct = st.sidebar.number_input(
    "Asumsi Premi XOL (%)", 0.0, 100.0, 14.07, 0.01
)

expense_pct = st.sidebar.number_input(
    "Asumsi Expense (%)", 0.0, 100.0, 15.00, 0.01
)

# =====================================================
# POLICY INFO
# =====================================================
st.subheader("📄 Informasi Polis")

c1, c2, c3 = st.columns(3)

with c1:
    nama_tertanggung = st.text_input("Nama Tertanggung", "")

with c2:
    start_date = st.date_input("Periode Mulai")

with c3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# SESSION STATE – COVERAGE TABLE
# =====================================================
if "rows" not in st.session_state:
    st.session_state.rows = []

def add_row():
    st.session_state.rows.append({
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI": 0.0,
        "Askrindo": 10.0,
        "Fakultatif": 0.0,
        "Komisi_Fak": 0.0,
        "LOL": 100.0,
        "Akuisisi": 15.0
    })

def delete_row(idx):
    st.session_state.rows.pop(idx)

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("📑 Input Coverage")

if st.button("➕ Tambah Coverage"):
    add_row()

for i, r in enumerate(st.session_state.rows):
    cols = st.columns([2,1,2,1,1,1,1,1,0.5])

    r["Coverage"] = cols[0].selectbox(
        "Coverage", COVERAGE_LIST,
        index=COVERAGE_LIST.index(r["Coverage"]),
        key=f"cov_{i}"
    )

    r["Rate"] = cols[1].number_input(
        "Rate (%)", value=r["Rate"], step=0.0001, format="%.5f", key=f"rate_{i}"
    )

    r["TSI"] = cols[2].number_input(
        "TSI IDR", value=r["TSI"], step=1.0, key=f"tsi_{i}"
    )

    r["Askrindo"] = cols[3].number_input(
        "% Askrindo", value=r["Askrindo"], step=1.0, key=f"ask_{i}"
    )

    r["Fakultatif"] = cols[4].number_input(
        "% Fakultatif", value=r["Fakultatif"], step=1.0, key=f"fac_{i}"
    )

    r["Komisi_Fak"] = cols[5].number_input(
        "% Komisi Fak", value=r["Komisi_Fak"], step=1.0, key=f"kom_{i}"
    )

    r["LOL"] = cols[6].number_input(
        "% LOL", value=r["LOL"], step=1.0, key=f"lol_{i}"
    )

    r["Akuisisi"] = cols[7].number_input(
        "% Akuisisi", value=r["Akuisisi"], step=1.0, key=f"akq_{i}"
    )

    if cols[8].button("🗑️", key=f"del_{i}"):
        delete_row(i)
        st.experimental_rerun()

# =====================================================
# CALCULATION
# =====================================================
if st.button("🚀 Calculate") and st.session_state.rows:

    results = []

    for r in st.session_state.rows:

        m = MASTER[r["Coverage"]]

        Exposure = r["TSI"]
        OR_cap = m["OR_Cap"]

        OR = min(Exposure, OR_cap)

        S_ask = OR * r["Askrindo"] / 100

        pool_amt = min(
            m["%pool"]/100 * S_ask,
            m["Amount_Pool"]
        )

        fac_amt = OR * r["Fakultatif"] / 100

        OR_amt = max(S_ask - pool_amt - fac_amt, 0)

        shortfall = max(OR - (pool_amt + fac_amt + OR_amt), 0)

        rate = r["Rate"] / 100
        lol = r["LOL"] / 100

        prem_100 = rate * lol * Exposure
        prem_ask = prem_100 * r["Askrindo"] / 100
        prem_or = prem_100 * OR_amt / Exposure if Exposure > 0 else 0

        rate_min = m["Rate_Min"]

        if pd.notna(rate_min):
            EL = rate_min * loss_ratio * Exposure * r["Askrindo"] / 100
        else:
            EL = loss_ratio * prem_ask

        XOL = prem_or * (premi_xol_pct / 100)
        expense = prem_ask * (expense_pct / 100)

        result = (
            prem_ask
            - EL
            - XOL
            - expense
        )

        results.append({
            "Prem_Askrindo": prem_ask,
            "Prem_OR": prem_or,
            "EL_Askrindo": EL,
            "XOL": XOL,
            "Expense": expense,
            "Result": result,
            "%Result": result / prem_ask if prem_ask else 0
        })

    df_res = pd.DataFrame(results)
    total = df_res.sum(numeric_only=True)
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df_res.loc["TOTAL"] = total

    st.subheader("📈 Hasil Profitability")
    st.dataframe(df_res)

    # =====================================================
    # PDF EXPORT
    # =====================================================
    def export_pdf():
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        content = []
        content.append(Paragraph("<b>Profitability Result</b>", styles["Title"]))
        content.append(Paragraph(f"Nama Tertanggung: {nama_tertanggung}", styles["Normal"]))
        content.append(Paragraph(f"Periode: {start_date} s/d {end_date}", styles["Normal"]))
        content.append(Paragraph(
            f"Asumsi: LR={loss_ratio}, XOL={premi_xol_pct}%, Expense={expense_pct}%",
            styles["Normal"]
        ))

        table_data = [df_res.reset_index().columns.tolist()] + \
                     df_res.reset_index().values.tolist()

        content.append(Table(table_data))
        doc.build(content)

        return buffer.getvalue()

    pdf = export_pdf()
    st.download_button(
        "📄 Download PDF",
        pdf,
        file_name=f"profitability_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf"
    )
