# =====================================================
# HELPER UNTUK PDF (HEADER & FORMAT)
# =====================================================
from reportlab.lib.styles import ParagraphStyle

header_style = ParagraphStyle(
    name="TableHeader",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    alignment=1  # CENTER
)

subtitle_style = ParagraphStyle(
    name="Subtitle",
    fontName="Helvetica",
    fontSize=11,
    leading=14,
    alignment=1  # CENTER
)

def format_header(col):
    return Paragraph(
        col.replace("_", "<br/>"),
        header_style
    )

def fmt(x):
    if isinstance(x, (int, float)):
        return f"{x:,.0f}"
    return x

# =====================================================
# PDF GENERATOR (LANDSCAPE)
# =====================================================
def generate_pdf(df):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(
        "<b>Profitability Checking Asuransi Umum</b>",
        styles["Title"]
    ))

    elements.append(Paragraph(
        "PT Asuransi Kredit Indonesia",
        subtitle_style
    ))

    elements.append(Spacer(1, 16))


    elements.append(Paragraph(f"Nama Tertanggung : {nama_tertanggung}", styles["Normal"]))
    elements.append(Paragraph(
    f"Start Date : {start_date.strftime('%d/%m/%Y')}",
    styles["Normal"]
    ))
    elements.append(Paragraph(
        f"End Date : {end_date.strftime('%d/%m/%Y')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Asumsi Digunakan</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Asumsi Loss Ratio : {LOSS_RATIO:.2%}", styles["Normal"]))
    elements.append(Paragraph(f"Premi XOL (%) : {XOL_RATE:.2%}", styles["Normal"]))
    elements.append(Paragraph(f"Expense Ratio : {EXP_RATIO:.2%}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    header = [format_header(c) for c in df.columns]
    body = []
    for _, row in df.iterrows():
        formatted_row = []
        for col, val in row.items():
            if col == "%Result":
                formatted_row.append(f"{val:.2%}")
            else:
                formatted_row.append(fmt(val))
        body.append(formatted_row)

    table_data = [header] + body



    # ===============================
    # AUTO-FIT TABLE WIDTH
    # ===============================
    page_width, _ = landscape(A4)
    usable_width = page_width - 60   # 30 left + 30 right margin
    n_cols = len(df.columns)
    col_widths = [usable_width / n_cols] * n_cols
    
    table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=1
    )
    table.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),

    # HEADER
    ("ALIGN", (0,0), (-1,0), "CENTER"),
    ("VALIGN", (0,0), (-1,0), "MIDDLE"),

    # BODY
    ("ALIGN", (1,1), (-1,-1), "RIGHT"),

    # FONT
    ("FONTSIZE", (0,0), (-1,-1), 8),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),

    # TOTAL ROW
    ("BACKGROUND", (0,-1), (-1,-1), colors.whitesmoke),
    ]))



    elements.append(table)
    elements.append(Spacer(1, 24))

    elements.append(Paragraph(
    f"Tanggal Export : {date.today().strftime('%d/%m/%Y')}",
    styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Disusun oleh,<br/>{user_name}",
        styles["Normal"]
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
