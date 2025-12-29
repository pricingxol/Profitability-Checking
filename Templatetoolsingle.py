import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")
st.caption("Logic final – TSI based, match Excel & bulk structure")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
MASTER_FILE = "Master File.xlsx"

@st.cache_data
def load_master():
    df = pd.read_excel(MASTER_FILE, sheet_name="master coverage")
    df.columns = df.columns.str.strip()
    return df

df_master = load_master()
MASTER = df_master.set_index("Coverage").to_dict("index")
COVERAGE_LIST = df_master["Coverage"].tolist()

# =====================================================
# SIDEBAR – ASSUMPTIONS
# =====================================================
st.sidebar.header("⚙️ Asumsi Profitability")

loss_ratio = st.sidebar.number_input(
    "Loss Ratio", 0.0, 1.0, 0.40, 0.01
)

premi_xol_pct = st.sidebar.number_input(
    "Premi XOL (%)", 0.0, 100.0, 14.07, 0.01
)

expense_pct = st.sidebar.number_input(
    "Expense (%)", 0.0, 100.0, 15.00, 0.01
)

# =====================================================
# POLICY INFO
# =====================================================
st.subheader("📄 Informasi Polis")

c1, c2, c3 = st.columns(3)
with c1:
    insured = st.text_input("Nama Tertanggung", "")
with c2:
    start_date = st.date_input("Periode Mulai")
with c3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# SESSION STATE – INPUT ROWS
# =====================================================
def default_row():
    return {
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI": "",
        "Askrindo": 10.0,
        "Fakultatif": 0.0,
        "Komisi_Fak": 0.0,
        "LOL": 100.0,
        "Akuisisi": 15.0
    }

if "rows" not in st.session_state:
    st.session_state.rows = [default_row()]

# =====================================================
# INPUT TABLE (MANUAL)
# =====================================================
st.subheader("🧾 Input Coverage")

if st.button("➕ Tambah Coverage"):
    st.session_state.rows.append(default_row())

for i, r in enumerate(st.session_state.rows):
    cols = st.columns([2,1,2,1,1,1,1,1,0.5])

    r["Coverage"] = cols[0].selectbox(
        "Coverage", COVERAGE_LIST,
        index=COVERAGE_LIST.index(r["Coverage"]),
        key=f"cov_{i}"
    )

    r["Rate"] = cols[1].number_input(
        "Rate (%)", value=r["Rate"], step=0.0001,
        format="%.5f", key=f"rate_{i}"
    )

    r["TSI"] = cols[2].text_input(
        "TSI IDR", value=str(r["TSI"]), key=f"tsi_{i}"
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

    if cols[8].button("🗑", key=f"del_{i}"):
        st.session_state.rows.pop(i)
        st.experimental_rerun()

# =====================================================
# CORE ENGINE (FINAL – LOCKED)
# =====================================================
def to_float(x):
    try:
        return float(str(x).replace(",", ""))
    except:
        return 0.0

def calculate(rows):
    results = []

    for r in rows:
        m = MASTER[r["Coverage"]]

        TSI = to_float(r["TSI"])
        pct_ask = r["Askrindo"] / 100
        pct_fac = r["Fakultatif"] / 100

        # ===== TSI SPREADING =====
        TSI_ask = pct_ask * TSI

        TSI_pool = min(
            m["%pool"] * TSI_ask,
            m["Amount_Pool"] * pct_ask
        )

        TSI_fac = pct_fac * TSI_ask
        TSI_or = TSI_ask - TSI_pool - TSI_fac

        # ===== PREMIUM =====
        rate = r["Rate"] / 100
        lol = r["LOL"] / 100

        Prem100 = rate * lol * TSI

        Prem_POOL = (TSI_pool / TSI) * Prem100 if TSI > 0 else 0
        Prem_Fac  = (TSI_fac  / TSI) * Prem100 if TSI > 0 else 0
        Prem_OR   = (TSI_or   / TSI) * Prem100 if TSI > 0 else 0

        Prem_Askrindo = Prem_POOL + Prem_Fac + Prem_OR

        # ===== EL =====
        if pd.notna(m["Rate_Min"]):
            EL100 = m["Rate_Min"] * loss_ratio * TSI
        else:
            EL100 = loss_ratio * Prem100

        EL_POOL = (TSI_pool / TSI) * EL100 if TSI > 0 else 0
        EL_Fac  = (TSI_fac  / TSI) * EL100 if TSI > 0 else 0
        EL_OR   = (TSI_or   / TSI) * EL100 if TSI > 0 else 0

        # ===== COST =====
        Prem_XOL = (premi_xol_pct / 100) * Prem_OR
        Expense  = (expense_pct / 100) * Prem_Askrindo
        Akuisisi = (r["Akuisisi"] / 100) * Prem_Askrindo

        # ===== RESULT =====
        Result = (
            Prem_Askrindo
            - Prem_POOL
            - Prem_Fac
            - Akuisisi
            + (m["Komisi_Pool"] * Prem_POOL)
            + (r["Komisi_Fak"] / 100 * Prem_Fac)
            - EL_OR
            + EL_POOL
            + EL_Fac
            - Prem_XOL
            - Expense
        )

        results.append({
            "Coverage": r["Coverage"],
            "Prem_Askrindo": Prem_Askrindo,
            "Prem_OR": Prem_OR,
            "EL_Askrindo": EL_OR,
            "Prem_XOL": Prem_XOL,
            "Expense": Expense,
            "Result": Result,
            "%Result": Result / Prem_Askrindo if Prem_Askrindo else 0
        })

    df = pd.DataFrame(results)
    total = df.select_dtypes("number").sum()
    total["Coverage"] = "TOTAL"
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]
    df = pd.concat([df, total.to_frame().T], ignore_index=True)

    return df

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    df_res = calculate(st.session_state.rows)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        df_res.style
        .format("{:,.0f}", subset=[
            "Prem_Askrindo","Prem_OR","EL_Askrindo",
            "Prem_XOL","Expense","Result"
        ])
        .format("{:.2%}", subset=["%Result"]),
        use_container_width=True
    )

    # =================================================
    # PDF EXPORT (RAPIH)
    # =================================================
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24
    )

    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("<b>Profitability Result</b>", styles["Title"]))
    elems.append(Paragraph(
        f"Tertanggung: {insured}<br/>"
        f"Periode: {start_date} s/d {end_date}<br/>"
        f"Asumsi: LR={loss_ratio:.2%}, XOL={premi_xol_pct:.2f}%, Expense={expense_pct:.2f}%",
        styles["Normal"]
    ))

    table_data = [df_res.columns.tolist()] + [
        [
            f"{v:,.0f}" if isinstance(v,(int,float)) and c not in ["%Result"]
            else f"{v:.2%}" if c=="%Result"
            else v
            for c,v in row.items()
        ]
        for _, row in df_res.iterrows()
    ]

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.5,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
        ("ALIGN",(1,1),(-1,-1),"RIGHT"),
        ("FONT",(0,-1),(-1,-1),"Helvetica-Bold")
    ]))

    elems.append(table)
    doc.build(elems)

    st.download_button(
        "📄 Download PDF",
        buffer.getvalue(),
        file_name=f"Profitability_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf"
    )
