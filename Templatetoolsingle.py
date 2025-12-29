import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="📊 Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.markdown("## 📊 **Profitability Checking – Akseptasi Manual**")
st.caption("Versi Excel-driven | Logic match Bulk Profitability")

# =====================================================
# LOAD MASTER EXCEL
# =====================================================
@st.cache_data
def load_master():
    df = pd.read_excel("Master File.xlsx", sheet_name="master coverage")
    df.columns = df.columns.str.strip()
    return df

df_master = load_master()

MASTER = {
    r["Coverage"]: {
        "rate_min": r["Rate_Min"] if not pd.isna(r["Rate_Min"]) else None,
        "or_cap": r["OR_Cap"],
        "pool": r["%pool"],
        "pool_cap": r["Amount_Pool"] if not pd.isna(r["Amount_Pool"]) else 0,
        "kom_pool": r["Komisi_Pool"]
    }
    for _, r in df_master.iterrows()
}

COVERAGE_LIST = df_master["Coverage"].tolist()

# =====================================================
# POLICY INFO
# =====================================================
st.markdown("### 📄 Informasi Polis")
c1, c2, c3 = st.columns(3)

with c1:
    insured = st.text_input("Nama Tertanggung", "PT CONTOH TERTANGGUNG")
with c2:
    start_date = st.date_input("Periode Mulai")
with c3:
    end_date = st.date_input("Periode Akhir")

# =====================================================
# ASSUMPTIONS
# =====================================================
st.sidebar.markdown("## ⚙️ Asumsi Profitability")

loss_ratio    = st.sidebar.number_input("Loss Ratio", 0.0, 1.0, 0.40, 0.01)
premi_xol_pct = st.sidebar.number_input("Premi XOL (%)", 0.0, 100.0, 12.0, 0.01)
expense_pct   = st.sidebar.number_input("Expense (%)", 0.0, 100.0, 15.0, 0.01)

premi_xol  = premi_xol_pct / 100
expense_rt = expense_pct / 100

# =====================================================
# INPUT TABLE INIT
# =====================================================
if "df_input" not in st.session_state:
    st.session_state.df_input = pd.DataFrame({
        "Delete": [False],
        "Coverage": [COVERAGE_LIST[0]],
        "Rate (%)": [0.0],
        "TSI_IDR": [0.0],
        "% Askrindo": [10.0],
        "% Fakultatif": [0.0],
        "% Komisi Fakultatif": [0.0],
        "% LOL": [100.0],
        "% Akuisisi": [15.0],
    })

# =====================================================
# INPUT TABLE
# =====================================================
st.markdown("### 🧾 Input Coverage")

edited = st.data_editor(
    st.session_state.df_input,
    column_config={
        "Delete": st.column_config.CheckboxColumn("🗑"),
        "Coverage": st.column_config.SelectboxColumn("Coverage", options=COVERAGE_LIST),
        "Rate (%)": st.column_config.NumberColumn("Rate (%)", format="%.5f", step=0.00001),
        "TSI_IDR": st.column_config.NumberColumn("TSI IDR", format="%,.0f"),
    },
    use_container_width=True
)

# Delete rows
edited = edited[~edited["Delete"]].copy()
edited["Delete"] = False
st.session_state.df_input = edited

# Add row
if st.button("➕ Tambah Coverage"):
    st.session_state.df_input = pd.concat(
        [st.session_state.df_input,
         st.session_state.df_input.iloc[-1:].assign(Delete=False)],
        ignore_index=True
    )

# =====================================================
# CORE ENGINE
# =====================================================
def run_profitability(df):
    rows = []

    for _, r in df.iterrows():
        m = MASTER[r["Coverage"]]

        rate = r["Rate (%)"] / 100
        tsi  = r["TSI_IDR"]
        ask  = r["% Askrindo"] / 100
        fac  = r["% Fakultatif"] / 100

        exposure = min(tsi, m["or_cap"])
        S_ask = ask * exposure

        pool_amt = min(m["pool"] * S_ask, m["pool_cap"] * ask) if m["pool"] > 0 else 0
        fac_amt  = fac * exposure
        OR_amt   = max(S_ask - pool_amt - fac_amt, 0)

        prem100  = rate * tsi
        prem_ask = prem100 * ask
        prem_or  = prem100 * (OR_amt / exposure) if exposure > 0 else 0

        # Expected Loss
        if m["rate_min"] is not None:
            EL_100 = m["rate_min"] * tsi * loss_ratio
        else:
            EL_100 = loss_ratio * prem100

        EL_ask = EL_100 * ask

        XL_cost = premi_xol * prem_or
        expense = expense_rt * prem_ask
        acq     = (r["% Akuisisi"] / 100) * prem_ask

        result = prem_ask - acq - EL_ask - XL_cost - expense

        rows.append([
            r["Coverage"], exposure, prem_ask, prem_or,
            EL_ask, XL_cost, expense, result
        ])

    out = pd.DataFrame(rows, columns=[
        "Coverage","Exposure_OR","Prem_Askrindo","Prem_OR",
        "EL_Askrindo","XOL","Expense","Result"
    ])

    total = out[["Exposure_OR","Prem_Askrindo","Prem_OR","EL_Askrindo","XOL","Expense","Result"]].sum()
    total["Coverage"] = "TOTAL"
    out = pd.concat([out, total.to_frame().T], ignore_index=True)

    out["%Result"] = out["Result"] / out["Prem_Askrindo"]

    return out

# =====================================================
# RUN
# =====================================================
if st.button("🚀 Calculate"):
    res = run_profitability(st.session_state.df_input)

    st.markdown("### 📈 Hasil Profitability")
    st.dataframe(
        res.style
        .format("{:,.0f}", subset=res.columns[1:-1])
        .format("{:.2%}", subset=["%Result"]),
        use_container_width=True
    )

    # =================================================
    # PDF EXPORT
    # =================================================
    def export_pdf(df):
        pdf = FPDF(orientation="L")
        pdf.add_page()
        pdf.set_font("Arial", size=9)

        pdf.cell(0, 8, f"Profitability Result – {insured}", ln=1)
        pdf.cell(0, 6, f"Periode: {start_date} s/d {end_date}", ln=1)
        pdf.cell(
            0, 6,
            f"Loss Ratio: {loss_ratio:.2%} | XOL: {premi_xol_pct:.2f}% | Expense: {expense_pct:.2f}%",
            ln=1
        )
        pdf.ln(4)

        for col in df.columns:
            pdf.cell(35, 6, col, border=1)
        pdf.ln()

        for _, row in df.iterrows():
            for v in row:
                pdf.cell(35, 6, f"{v:,.0f}" if isinstance(v,(int,float)) else str(v), border=1)
            pdf.ln()

        return pdf.output(dest="S").encode("latin-1")

    pdf_bytes = export_pdf(res)

    st.download_button(
        "📄 Download PDF",
        pdf_bytes,
        file_name=f"Profitability_{insured}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf"
    )
