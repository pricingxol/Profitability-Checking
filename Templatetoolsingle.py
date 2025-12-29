import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="Profitability Checking – Akseptasi Manual",
    layout="wide"
)

st.title("📊 Profitability Checking – Akseptasi Manual")

# =====================================================
# LOAD MASTER COVERAGE (BACKEND ONLY)
# =====================================================
MASTER_FILE = "Master File.xlsx"

df_master = pd.read_excel(MASTER_FILE, sheet_name="master coverage")
df_master.columns = [c.strip() for c in df_master.columns]

# expected columns:
# Coverage | Rate_Min | OR_Cap

coverage_list = df_master["Coverage"].tolist()
master_map = df_master.set_index("Coverage").to_dict(orient="index")

# =====================================================
# ASSUMPTIONS (SIDEBAR)
# =====================================================
st.sidebar.header("Asumsi Profitability")

loss_ratio = st.sidebar.number_input("Asumsi Loss Ratio", 0.0, 1.0, 0.45, 0.01)
premi_xol = st.sidebar.number_input("Asumsi Premi XOL", 0.0, 1.0, 0.12, 0.01)
expense_ratio = st.sidebar.number_input("Asumsi Expense", 0.0, 1.0, 0.20, 0.01)

# =====================================================
# CONSTANTS (IDENTIK BULK)
# =====================================================
KOMISI_BPPDAN = 0.35
KOMISI_MAIPARK = 0.30

RATE_MB_INDUSTRIAL = 0.0015
RATE_MB_NON_INDUSTRIAL = 0.0001
RATE_PL = 0.0005
RATE_FG = 0.0010

# =====================================================
# METADATA POLIS
# =====================================================
st.subheader("📄 Informasi Polis")

insured = st.text_input("Nama Tertanggung")
start_date = st.date_input("Periode Mulai")
end_date = st.date_input("Periode Akhir")

# =====================================================
# INPUT COVERAGE (STREAMLIT FORM)
# =====================================================
st.subheader("📋 Input Coverage")

default_row = {
    "Coverage": coverage_list[0],
    "Rate": 0.001,
    "TSI_IDR": 0.0,
    "Limit_IDR": 0.0,
    "TopRisk_IDR": 0.0,
    "% Askrindo Share": 1.0,
    "% Fakultatif Share": 0.0,
    "% Komisi Fakultatif": 0.0,
    "% LOL Premi": 1.0,    # DEFAULT 100%
    "% Akuisisi": 0.15     # DEFAULT 15%
}

if "rows" not in st.session_state:
    st.session_state.rows = [default_row]

def add_row():
    st.session_state.rows.append(default_row.copy())

st.button("➕ Tambah Coverage", on_click=add_row)

df_input = pd.DataFrame(st.session_state.rows)

edited = st.data_editor(
    df_input,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Coverage": st.column_config.SelectboxColumn(
            options=coverage_list
        )
    }
)

# =====================================================
# CORE ENGINE (IDENTIK BULK – MANUAL VERSION)
# =====================================================
def run_profitability(row):

    cov = row["Coverage"]
    rate_min = master_map[cov]["Rate_Min"]
    or_cap = master_map[cov]["OR_Cap"]

    # ===== Exposure =====
    ExposureBasis = max(row["Limit_IDR"], row["TopRisk_IDR"])
    Exposure_OR = min(ExposureBasis, or_cap)

    S_Askrindo = row["% Askrindo Share"] * Exposure_OR

    # ===== POOL (SPREADING ONLY) =====
    if cov.upper().startswith("FIRE") or cov.upper() == "PAR":
        Pool_amt = min(
            0.025 * S_Askrindo,
            500_000_000 * row["% Askrindo Share"]
        )
        komisi_pool = KOMISI_BPPDAN

    elif cov.upper().startswith("EQVET"):
        rate_pool = 0.10 if "DKI" in cov.upper() or "JABAR" in cov.upper() or "BANTEN" in cov.upper() else 0.25
        Pool_amt = min(
            rate_pool * S_Askrindo,
            10_000_000_000 * row["% Askrindo Share"]
        )
        komisi_pool = KOMISI_MAIPARK

    else:
        Pool_amt = 0
        komisi_pool = 0

    Fac_amt = row["% Fakultatif Share"] * Exposure_OR
    OR_amt = max(S_Askrindo - Pool_amt - Fac_amt, 0)

    Shortfall_amt = max(
        Exposure_OR - (Pool_amt + Fac_amt + OR_amt), 0
    )

    pct_pool = Pool_amt / Exposure_OR if Exposure_OR > 0 else 0

    # ===== PREMIUM =====
    Prem100 = row["Rate"] * row["% LOL Premi"] * row["TSI_IDR"]

    Prem_Askrindo_Normal = Prem100 * row["% Askrindo Share"]
    Prem_Shortfall = row["Rate"] * row["% LOL Premi"] * Shortfall_amt
    Prem_Askrindo = Prem_Askrindo_Normal + Prem_Shortfall

    Prem_POOL = Prem100 * pct_pool
    Prem_Fac = Prem100 * row["% Fakultatif Share"]

    Acq_amt = row["% Akuisisi"] * Prem_Askrindo
    Komisi_POOL = komisi_pool * Prem_POOL
    Komisi_Fak = row["% Komisi Fakultatif"] * Prem_Fac

    # ===== EXPECTED LOSS (RULE KAMU) =====
    if pd.isna(rate_min):
        # TIDAK ADA RATE MIN → EL = LR × PREMI
        EL_100 = loss_ratio * Prem100
    else:
        # ADA RATE MIN → EL = rate_min × Exposure × LR
        EL_100 = rate_min * ExposureBasis * loss_ratio

    EL_Askrindo_Normal = EL_100 * row["% Askrindo Share"]
    EL_Shortfall = (
        EL_100 * (Shortfall_amt / ExposureBasis)
        if ExposureBasis > 0 else 0
    )
    EL_Askrindo = EL_Askrindo_Normal + EL_Shortfall

    EL_POOL = EL_100 * pct_pool
    EL_Fac = EL_100 * row["% Fakultatif Share"]

    # ===== COST =====
    XL_cost = premi_xol * OR_amt
    Expense = expense_ratio * Prem_Askrindo

    # ===== RESULT =====
    Result = (
        Prem_Askrindo
        - Prem_POOL
        - Prem_Fac
        - Acq_amt
        + Komisi_POOL
        + Komisi_Fak
        - EL_Askrindo
        + EL_POOL
        + EL_Fac
        - XL_cost
        - Expense
    )

    Result_pct = Result / Prem_Askrindo if Prem_Askrindo != 0 else 0

    return {
        "Exposure_OR": Exposure_OR,
        "Prem_Askrindo": Prem_Askrindo,
        "EL_Askrindo": EL_Askrindo,
        "Result": Result,
        "%Result": Result_pct
    }

# =====================================================
# RUN CALCULATION
# =====================================================
if st.button("🚀 Calculate"):

    output = []
    warnings = []

    for _, r in edited.iterrows():
        res = run_profitability(r)
        output.append({**r.to_dict(), **res})

        # ===== VALIDATION =====
        cov = r["Coverage"]
        rate_min = master_map[cov]["Rate_Min"]
        if not pd.isna(rate_min) and r["Rate"] < rate_min:
            warnings.append(f"⚠️ Rate di bawah minimum untuk {cov}")

        if max(r["Limit_IDR"], r["TopRisk_IDR"]) > master_map[cov]["OR_Cap"]:
            warnings.append(f"⚠️ OR melebihi maksimum untuk {cov}")

    df_result = pd.DataFrame(output)

    st.subheader("📈 Hasil Profitability")
    st.dataframe(df_result, use_container_width=True)

    for w in warnings:
        st.warning(w)

    # =================================================
    # EXPORT EXCEL
    # =================================================
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_result.to_excel(writer, sheet_name="Detail", index=False)

    buffer.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    st.download_button(
        "⬇️ Download Excel",
        buffer,
        file_name=f"Profitability_{insured}_{ts}.xlsx"
    )

    # =================================================
    # EXPORT PDF
    # =================================================
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("<b>Profitability Checking – Akseptasi</b>", styles["Title"]))
    elements.append(Paragraph(f"Nama Tertanggung: {insured}", styles["Normal"]))
    elements.append(Paragraph(f"Periode Polis: {start_date} – {end_date}", styles["Normal"]))
    elements.append(Paragraph(
        f"Diexport: {datetime.now().strftime('%d %b %Y | %H:%M WIB')}",
        styles["Normal"]
    ))

    table_data = [df_result.columns.tolist()] + df_result.round(0).values.tolist()
    elements.append(Table(table_data))

    doc.build(elements)
    pdf_buffer.seek(0)

    st.download_button(
        "⬇️ Download PDF",
        pdf_buffer,
        file_name=f"Profitability_{insured}_{ts}.pdf"
    )
