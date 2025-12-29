import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")

# ===============================
# LOAD MASTER FILE
# ===============================
MASTER_FILE = "Master File.xlsx"
df_master = pd.read_excel(MASTER_FILE)
df_master["Coverage"] = df_master["Coverage"].astype(str)
master = df_master.set_index("Coverage").to_dict("index")
coverage_list = list(master.keys())

# ===============================
# ASSUMPTIONS
# ===============================
st.sidebar.header("Asumsi Profitability")

loss_ratio = st.sidebar.number_input("Loss Ratio", 0.0, 1.0, 0.40, 0.01)
premi_xol = st.sidebar.number_input("Premi XOL (%)", 0.0, 100.0, 14.07, 0.01) / 100
expense = st.sidebar.number_input("Expense (%)", 0.0, 100.0, 15.0, 0.01) / 100

# ===============================
# POLICY INFO
# ===============================
st.subheader("📄 Informasi Polis")
insured = st.text_input("Nama Tertanggung")
sdate = st.date_input("Periode Mulai")
edate = st.date_input("Periode Akhir")

# ===============================
# INPUT TABLE
# ===============================
st.subheader("📋 Input Coverage")

if "rows" not in st.session_state:
    st.session_state.rows = 1

def add_row():
    st.session_state.rows += 1

df_input = pd.DataFrame({
    "Coverage": [coverage_list[0]] * st.session_state.rows,
    "Rate (%)": [0.0] * st.session_state.rows,
    "TSI_IDR": [0.0] * st.session_state.rows,
    "% Askrindo": [10.0] * st.session_state.rows,
    "% Fakultatif": [0.0] * st.session_state.rows,
    "% Komisi Fakultatif": [0.0] * st.session_state.rows,
    "% LOL": [100.0] * st.session_state.rows,
    "% Akuisisi": [15.0] * st.session_state.rows,
})

df_edit = st.data_editor(
    df_input,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "Coverage": st.column_config.SelectboxColumn("Coverage", options=coverage_list)
    }
)

st.button("➕ Tambah Coverage", on_click=add_row)

# ===============================
# CORE ENGINE
# ===============================
def calc(row):
    m = master[row["Coverage"]]

    rate = row["Rate (%)"] / 100
    ask = row["% Askrindo"] / 100
    fac = row["% Fakultatif"] / 100
    lol = row["% LOL"] / 100
    acq = row["% Akuisisi"] / 100
    kom_fac = row["% Komisi Fakultatif"] / 100

    exposure = row["TSI_IDR"]
    S_ask = ask * exposure

    pool_pct = (m["%pool"] or 0) / 100
    pool_cap = m["Amount_Pool"] or 0
    kom_pool = (m["Komisi_Pool"] or 0) / 100

    pool_amt = min(pool_pct * S_ask, pool_cap * ask)
    fac_amt = fac * exposure

    OR_raw = S_ask - pool_amt - fac_amt
    OR_amt = min(OR_raw, m["OR_Cap"])

    Prem100 = rate * lol * exposure
    Prem_ask = ask * Prem100
    Prem_OR = (OR_amt / exposure) * Prem100 if exposure else 0
    Prem_pool = (pool_amt / exposure) * Prem100 if exposure else 0
    Prem_fac = fac * Prem100

    if pd.isna(m["Rate_Min"]):
        EL100 = loss_ratio * Prem100
    else:
        EL100 = m["Rate_Min"] * loss_ratio * exposure

    EL_ask = ask * EL100
    EL_pool = (pool_amt / exposure) * EL100 if exposure else 0
    EL_fac = fac * EL100

    akuisisi = acq * Prem_ask
    xol = premi_xol * Prem_OR
    exp = expense * Prem_ask
    kom_pool_amt = kom_pool * Prem_pool
    kom_fac_amt = kom_fac * Prem_fac

    result = (
        Prem_ask
        - Prem_pool
        - Prem_fac
        - akuisisi
        + kom_pool_amt
        + kom_fac_amt
        - EL_ask
        + EL_pool
        + EL_fac
        - xol
        - exp
    )

    return pd.Series({
        "Prem_Askrindo": Prem_ask,
        "Prem_OR": Prem_OR,
        "EL_Askrindo": EL_ask,
        "XOL": xol,
        "Expense": exp,
        "Result": result
    })

# ===============================
# CALCULATE
# ===============================
if st.button("🚀 Calculate"):
    res = df_edit.apply(calc, axis=1)
    res["%Result"] = res["Result"] / res["Prem_Askrindo"]

    total = res.sum(numeric_only=True)
    total["%Result"] = total["Result"] / total["Prem_Askrindo"]
    res.loc["TOTAL"] = total

    st.subheader("📈 Hasil Profitability")
    st.dataframe(
        res.style.format({
            "Prem_Askrindo": "{:,.0f}",
            "Prem_OR": "{:,.0f}",
            "EL_Askrindo": "{:,.0f}",
            "XOL": "{:,.0f}",
            "Expense": "{:,.0f}",
            "Result": "{:,.0f}",
            "%Result": "{:.2%}"
        }),
        use_container_width=True
    )

    # ===============================
    # PDF EXPORT
    # ===============================
    def export_pdf(df):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("<b>Profitability Checking Result</b>", styles["Title"]))
        elements.append(Paragraph(f"Nama Tertanggung: {insured}", styles["Normal"]))
        elements.append(Paragraph(f"Periode: {sdate} s/d {edate}", styles["Normal"]))
        elements.append(Paragraph(f"Exported: {datetime.now()}", styles["Normal"]))
        elements.append(Paragraph("<br/>", styles["Normal"]))

        elements.append(Paragraph(
            f"Asumsi: Loss Ratio {loss_ratio:.0%}, XOL {premi_xol:.2%}, Expense {expense:.0%}",
            styles["Normal"]
        ))
        elements.append(Paragraph("<br/>", styles["Normal"]))

        table_data = [["Item"] + list(df.columns)]
        for idx, row in df.iterrows():
            table_data.append([str(idx)] + [f"{v:,.0f}" if isinstance(v, (int, float)) else v for v in row])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT")
        ]))

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer

    pdf = export_pdf(res)
    st.download_button(
        "📄 Download PDF",
        pdf,
        file_name=f"Profitability_{insured}_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf"
    )
