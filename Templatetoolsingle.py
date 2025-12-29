import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

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

df_master = pd.read_excel(MASTER_FILE)
df_master.columns = [c.strip() for c in df_master.columns]

MASTER = df_master.set_index("Coverage").to_dict("index")
COVERAGE_LIST = list(MASTER.keys())

# =====================================================
# SIDEBAR ASSUMPTIONS
# =====================================================
st.sidebar.header("⚙️ Asumsi Profitability")

LOSS_RATIO = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.40, 0.01)
XOL_RATE = st.sidebar.number_input("Asumsi Premi XOL (%)", 0.0, 100.0, 14.07) / 100
EXPENSE_RATE = st.sidebar.number_input("Asumsi Expense (%)", 0.0, 100.0, 15.0) / 100

# =====================================================
# INFORMASI POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

c1, c2, c3 = st.columns(3)
with c1:
    tertanggung = st.text_input("Nama Tertanggung", "")
with c2:
    start_date = st.date_input("Periode Mulai")
with c3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# SESSION STATE
# =====================================================
if "rows" not in st.session_state:
    st.session_state.rows = []

def add_row():
    st.session_state.rows.append({
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI": 0.0,
        "%Askrindo": 10.0,
        "%Fakultatif": 0.0,
        "%KomisiFak": 0.0,
        "%LOL": 100.0,
        "%Akuisisi": 15.0
    })

def delete_row(i):
    st.session_state.rows.pop(i)

# =====================================================
# INPUT COVERAGE
# =====================================================
st.subheader("🧾 Input Coverage")

st.button("➕ Tambah Coverage", on_click=add_row)

for i, r in enumerate(st.session_state.rows):
    cols = st.columns([2,1,2,1,1,1,1,1,0.4])

    r["Coverage"] = cols[0].selectbox(
        "Coverage", COVERAGE_LIST, COVERAGE_LIST.index(r["Coverage"]), key=f"cov{i}"
    )
    r["Rate"] = cols[1].number_input("Rate (%)", value=r["Rate"], format="%.5f", key=f"rate{i}")
    r["TSI"] = cols[2].number_input("TSI IDR", value=r["TSI"], format="%.0f", key=f"tsi{i}")
    r["%Askrindo"] = cols[3].number_input("% Askrindo", value=r["%Askrindo"], key=f"ask{i}")
    r["%Fakultatif"] = cols[4].number_input("% Fakultatif", value=r["%Fakultatif"], key=f"fac{i}")
    r["%KomisiFak"] = cols[5].number_input("% Komisi Fak", value=r["%KomisiFak"], key=f"kom{i}")
    r["%LOL"] = cols[6].number_input("% LOL", value=r["%LOL"], key=f"lol{i}")
    r["%Akuisisi"] = cols[7].number_input("% Akuisisi", value=r["%Akuisisi"], key=f"ak{i}")

    cols[8].button("🗑️", key=f"del{i}", on_click=delete_row, args=(i,))

# =====================================================
# CORE ENGINE
# =====================================================
def run_calc(r):
    m = MASTER[r["Coverage"]]

    rate = r["Rate"] / 100
    ask = r["%Askrindo"] / 100
    fac = r["%Fakultatif"] / 100
    lol = r["%LOL"] / 100
    acq = r["%Akuisisi"] / 100
    kom_fak = r["%KomisiFak"] / 100

    # Exposure OR (cap OR, NOT ourshare)
    Exposure_OR = min(r["TSI"], m["OR_Cap"])

    # Share TSI
    TSI_ask = ask * Exposure_OR
    TSI_fac = fac * Exposure_OR

    # Pool
    pool_pct = m["%pool"]
    pool_cap = m["Amount_Pool"] * ask
    Pool_amt = min(pool_pct * TSI_ask, pool_cap)

    # OR (Own Retention)
    OR_amt = max(TSI_ask - Pool_amt - TSI_fac, 0)

    # ===== PREMIUM =====
    Prem100 = rate * lol * r["TSI"]

    Prem_Askrindo = Prem100 * ask
    Prem_OR = Prem100 * (OR_amt / Exposure_OR if Exposure_OR else 0)
    Prem_POOL = Prem100 * (Pool_amt / Exposure_OR if Exposure_OR else 0)
    Prem_Fac = Prem100 * fac

    # ===== EL =====
    if pd.isna(m["Rate_Min"]):
        EL100 = Prem100 * LOSS_RATIO
    else:
        EL100 = m["Rate_Min"] * Exposure_OR * LOSS_RATIO

    EL_Askrindo = EL100 * ask

    # ===== COST =====
    XOL = XOL_RATE * Prem_OR
    Expense = EXPENSE_RATE * Prem_Askrindo

    Result = (
        Prem_Askrindo
        - Prem_POOL
        - Prem_Fac
        - acq * Prem_Askrindo
        + m["Komisi_Pool"] * Prem_POOL
        + kom_fak * Prem_Fac
        - EL_Askrindo
        - XOL
        - Expense
    )

    return {
        "Coverage": r["Coverage"],
        "Prem_Askrindo": Prem_Askrindo,
        "Prem_OR": Prem_OR,
        "EL_Askrindo": EL_Askrindo,
        "Prem_XOL": XOL,
        "Expense": Expense,
        "Result": Result,
        "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
    }

# =====================================================
# CALCULATE
# =====================================================
if st.button("🚀 Calculate") and st.session_state.rows:

    df = pd.DataFrame([run_calc(r) for r in st.session_state.rows])

    total = df.sum(numeric_only=True)
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df = pd.concat([df, pd.DataFrame([total])])

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df.style.format({
            "Prem_Askrindo": "{:,.0f}",
            "Prem_OR": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "Prem_XOL": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )

    # =====================================================
    # PDF EXPORT
    # =====================================================
    def export_pdf(df):
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("<b>Profitability Result</b>", styles["Title"]))
        story.append(Spacer(1, 12))

        meta = f"""
        Nama Tertanggung: {tertanggung}<br/>
        Periode: {start_date} s/d {end_date}<br/>
        Asumsi: LR={LOSS_RATIO:.0%}, XOL={XOL_RATE:.2%}, Expense={EXPENSE_RATE:.2%}
        """
        story.append(Paragraph(meta, styles["Normal"]))
        story.append(Spacer(1, 12))

        table_data = [df.columns.tolist()] + df.round(0).astype(str).values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT")
        ]))

        story.append(table)
        doc.build(story)
        buf.seek(0)
        return buf

    st.download_button(
        "📄 Download PDF",
        data=export_pdf(df),
        file_name=f"Profitability_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf"
    )
