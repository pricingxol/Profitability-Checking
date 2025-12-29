import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
MASTER_FILE = "Master File.xlsx"  # pastikan file ada di repo

@st.cache_data
def load_master():
    df = pd.read_excel(MASTER_FILE)
    df.columns = [c.strip() for c in df.columns]
    return df

df_master = load_master()
COVERAGE_LIST = df_master["Coverage"].tolist()

MASTER_MAP = (
    df_master
    .set_index("Coverage")
    .to_dict(orient="index")
)

# =====================================================
# SIDEBAR – ASUMSI
# =====================================================
st.sidebar.header("📌 Asumsi Profitability")

loss_ratio = st.sidebar.number_input(
    "Asumsi Loss Ratio",
    0.0, 1.0, 0.40, 0.01
)

premi_xol = st.sidebar.number_input(
    "Asumsi Premi XOL (%)",
    0.0, 100.0, 14.07, 0.01
) / 100

expense_ratio = st.sidebar.number_input(
    "Asumsi Expense (%)",
    0.0, 100.0, 15.0, 0.01
) / 100

# =====================================================
# INFORMASI POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

col1, col2, col3 = st.columns(3)

with col1:
    insured_name = st.text_input("Nama Tertanggung", "")

with col2:
    start_date = st.date_input("Periode Mulai")

with col3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE TABLE
# =====================================================
st.subheader("🧾 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = [{
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI_IDR": 0.0,
        "% Askrindo": 10.0,
        "% Fakultatif": 0.0,
        "% Komisi Fakultatif": 0.0,
        "% LOL": 100.0,
        "% Akuisisi": 15.0,
    }]

def add_row():
    st.session_state.rows.append({
        "Coverage": COVERAGE_LIST[0],
        "Rate": 0.0,
        "TSI_IDR": 0.0,
        "% Askrindo": 10.0,
        "% Fakultatif": 0.0,
        "% Komisi Fakultatif": 0.0,
        "% LOL": 100.0,
        "% Akuisisi": 15.0,
    })

def delete_row(idx):
    st.session_state.rows.pop(idx)

for i, row in enumerate(st.session_state.rows):
    c0, c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns(
        [0.4, 2, 1.2, 2, 1.2, 1.2, 1.5, 1.2, 1.2, 0.5]
    )

    with c0:
        if st.button("🗑️", key=f"del_{i}"):
            delete_row(i)
            st.experimental_rerun()

    with c1:
        row["Coverage"] = st.selectbox(
            "Coverage", COVERAGE_LIST,
            index=COVERAGE_LIST.index(row["Coverage"]),
            key=f"cov_{i}"
        )

    with c2:
        row["Rate"] = st.number_input(
            "Rate (%)", 0.0, step=0.00001,
            value=row["Rate"], format="%.5f",
            key=f"rate_{i}"
        )

    with c3:
        row["TSI_IDR"] = st.number_input(
            "TSI IDR",
            value=row["TSI_IDR"],
            step=1.0,
            key=f"tsi_{i}"
        )

    with c4:
        row["% Askrindo"] = st.number_input(
            "% Askrindo", 0.0, 100.0,
            value=row["% Askrindo"], step=0.1,
            key=f"ask_{i}"
        )

    with c5:
        row["% Fakultatif"] = st.number_input(
            "% Fakultatif", 0.0, 100.0,
            value=row["% Fakultatif"], step=0.1,
            key=f"fac_{i}"
        )

    with c6:
        row["% Komisi Fakultatif"] = st.number_input(
            "% Komisi Fakultatif", 0.0, 100.0,
            value=row["% Komisi Fakultatif"], step=0.1,
            key=f"komfac_{i}"
        )

    with c7:
        row["% LOL"] = st.number_input(
            "% LOL", 0.0, 100.0,
            value=row["% LOL"], step=1.0,
            key=f"lol_{i}"
        )

    with c8:
        row["% Akuisisi"] = st.number_input(
            "% Akuisisi", 0.0, 100.0,
            value=row["% Akuisisi"], step=0.1,
            key=f"akq_{i}"
        )

st.button("➕ Tambah Coverage", on_click=add_row)

# =====================================================
# CORE ENGINE
# =====================================================
def run_profitability(row):
    m = MASTER_MAP[row["Coverage"]]

    rate = row["Rate"] / 100
    ask = row["% Askrindo"] / 100
    fac = row["% Fakultatif"] / 100
    kom_fac = row["% Komisi Fakultatif"] / 100
    lol = row["% LOL"] / 100
    akq = row["% Akuisisi"] / 100

    tsi = row["TSI_IDR"]

    # Exposure OR (OWN RETENTION BASE)
    exposure_or = min(tsi, m["OR_Cap"])

    S_ask = ask * exposure_or

    pool_amt = 0
    if m["%pool"] > 0:
        pool_amt = min(
            m["%pool"] * S_ask,
            m["Amount_Pool"] * ask
        )

    fac_amt = fac * exposure_or
    OR_amt = max(S_ask - pool_amt - fac_amt, 0)

    prem_100 = rate * lol * tsi
    prem_ask = prem_100 * ask
    prem_or = rate * lol * OR_amt

    # EL
    if pd.notna(m["Rate_Min"]):
        el_100 = m["Rate_Min"] * loss_ratio * tsi
    else:
        el_100 = loss_ratio * prem_100

    el_ask = el_100 * ask

    # COST
    xl_cost = premi_xol * OR_amt
    expense = expense_ratio * prem_ask

    result = (
        prem_ask
        - akq * prem_ask
        - el_ask
        - xl_cost
        - expense
    )

    return {
        "Prem_Askrindo": prem_ask,
        "Prem_OR": prem_or,
        "EL_Askrindo": el_ask,
        "XOL": xl_cost,
        "Expense": expense,
        "Result": result
    }

# =====================================================
# CALCULATE
# =====================================================
if st.button("🚀 Calculate"):
    results = []
    for r in st.session_state.rows:
        out = run_profitability(r)
        results.append(out)

    df_res = pd.DataFrame(results)
    total = df_res.sum(numeric_only=True)
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]

    df_res["%Result"] = df_res["Result"] / df_res["Prem_Askrindo"]
    df_res.loc["TOTAL"] = total

    st.subheader("📊 Hasil Profitability")
    st.dataframe(
        df_res.style.format({
            "Prem_Askrindo": "{:,.0f}",
            "Prem_OR": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "XOL": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}",
        }),
        use_container_width=True
    )

    # =================================================
    # EXPORT PDF
    # =================================================
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("<b>Profitability Checking</b>", styles["Title"]))
    elems.append(Spacer(1, 12))
    elems.append(Paragraph(f"Tertanggung: {insured_name}", styles["Normal"]))
    elems.append(Paragraph(f"Periode: {start_date} – {end_date}", styles["Normal"]))
    elems.append(Paragraph(
        f"Asumsi: LR={loss_ratio:.2%}, XOL={premi_xol:.2%}, Expense={expense_ratio:.2%}",
        styles["Normal"]
    ))
    elems.append(Spacer(1, 12))

    table_data = [df_res.columns.tolist()] + df_res.round(0).astype(int).reset_index(drop=True).values.tolist()

    tbl = Table(table_data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))

    elems.append(tbl)
    doc.build(elems)

    st.download_button(
        "📄 Download PDF",
        buffer.getvalue(),
        file_name=f"Profitability_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf"
    )
