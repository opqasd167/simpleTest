"""Generates the PDF test documents for the KM demo.
Usage: python make_pdf.py <output_dir>
"""
import sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, ListFlowable, ListItem)

out = Path(sys.argv[1])
ss = getSampleStyleSheet()
TITLE = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, alignment=0, spaceAfter=6)
META = ParagraphStyle("M", parent=ss["Normal"], fontName="Helvetica-Oblique", fontSize=9.5,
                      textColor=colors.HexColor("#555555"), spaceAfter=14)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=11, leading=15, spaceAfter=7)


def bullets(items):
    return ListFlowable([ListItem(Paragraph(t, BODY), leftIndent=14) for t in items],
                        bulletType="bullet", start="•", leftIndent=14)


CELL = ParagraphStyle("C", parent=BODY, fontSize=10.5, leading=13, spaceAfter=0)
CELL_HEAD = ParagraphStyle("CH", parent=CELL, fontName="Helvetica-Bold")


def grid(rows, widths):
    wrapped = [[Paragraph(c, CELL_HEAD if r == 0 else CELL) for c in row] for r, row in enumerate(rows)]
    t = Table(wrapped, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7E6E6")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(inch, 0.6 * inch, doc.title)
    canvas.drawRightString(letter[0] - inch, 0.6 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build(name, title, story):
    doc = SimpleDocTemplate(str(out / name), pagesize=letter, title=title,
                            leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("wrote", name)


# ---------- Leave Policy (3 pages) ----------
leave = [
    Paragraph("Leave Policy", TITLE),
    Paragraph("Brightwave Analytics (fictional company for testing) - Policy HR-04 - "
              "Effective 1 January 2026 - Owner: People Team", META),
    Paragraph("1. Annual leave entitlement", H1),
    Paragraph("Annual leave depends on length of service, measured on 1 January of the leave year:", BODY),
    grid([["Length of service on 1 January", "Annual leave per year"],
          ["Less than 3 years", "20 working days"],
          ["3 years or more", "25 working days"]], [3.2 * inch, 3.2 * inch]),
    Spacer(1, 8),
    Paragraph("Employees who join during the year receive a pro-rated entitlement for their first year. "
              "Public holidays are in addition to annual leave.", BODY),
    Paragraph("2. Carrying over unused leave", H1),
    Paragraph("Up to 5 unused days of annual leave may be carried over into the next year. "
              "Carried-over days must be taken by 31 March; any carried-over days not taken by then are lost. "
              "Unused leave is not paid out, except when employment ends.", BODY),
    Paragraph("3. Requesting leave", H1),
    bullets(["Request leave in the HR portal before taking it.",
             "Absences of 5 or more consecutive working days must be requested at least 10 working days in advance.",
             "Managers approve or decline requests within 3 working days.",
             "No more than 2 people from the same team may be on leave on the same day."]),
    PageBreak(),
    Paragraph("4. Exceeding the entitlement", H1),
    Paragraph("Annual leave taken beyond an employee's entitlement for the year is unpaid. "
              "Any leave beyond the entitlement requires approval from the HR Director, in addition to the "
              "line manager. The People Team reviews leave balances every quarter and contacts employees who "
              "have exceeded their entitlement.", BODY),
    Paragraph("5. Sick leave", H1),
    Paragraph("Employees receive 10 days of paid sick leave per calendar year. Sick leave does not reduce "
              "the annual leave entitlement. A medical certificate is required for any absence longer than "
              "3 consecutive days. Report sickness to your line manager before 10:00 on the first day of absence.", BODY),
    Paragraph("6. Parental leave", H1),
    Paragraph("The primary caregiver receives 16 weeks of fully paid parental leave. The secondary caregiver "
              "receives 4 weeks of fully paid parental leave, which must be taken within 12 months of the birth "
              "or adoption.", BODY),
    PageBreak(),
    Paragraph("7. Other types of leave", H1),
    grid([["Type of leave", "Allowance", "Paid?"],
          ["Bereavement (close family)", "5 working days per event", "Yes"],
          ["Jury service", "As required by the court", "Yes"],
          ["Volunteering", "2 working days per year", "Yes"],
          ["Unpaid leave", "Up to 20 working days per year", "No"]],
         [2.6 * inch, 2.6 * inch, 1.2 * inch]),
    Spacer(1, 8),
    Paragraph("Unpaid leave requires approval from the line manager and the HR Director.", BODY),
    Paragraph("8. Questions", H1),
    Paragraph("Questions about this policy go to the People Team through the HR portal.", BODY),
]

# ---------- IT Security Policy (2 pages) ----------
security = [
    Paragraph("IT Security Policy", TITLE),
    Paragraph("Brightwave Analytics (fictional company for testing) - Policy IT-01 - "
              "Effective 1 January 2026 - Owner: IT Security", META),
    Paragraph("1. Passwords and sign-in", H1),
    bullets(["Passwords must be at least 14 characters long.",
             "Passwords must be changed every 90 days and may not reuse any of the last 5 passwords.",
             "Multi-factor authentication (MFA) is required for email, the VPN and every company system that supports it.",
             "Accounts are locked for 15 minutes after 5 failed sign-in attempts."]),
    Paragraph("2. Devices", H1),
    bullets(["Company laptops use full-disk encryption, which IT enables before the laptop is issued.",
             "Screens must lock automatically after 5 minutes of inactivity.",
             "Personal devices may be used for email only, and only through the approved mobile app.",
             "USB storage devices are blocked on company laptops."]),
    Paragraph("3. Data classification", H1),
    Paragraph("All company data belongs to one of four classification levels:", BODY),
    grid([["Level", "Examples", "Rules"],
          ["Public", "Website content, press releases", "No restrictions"],
          ["Internal", "Policies, team plans", "Employees only"],
          ["Confidential", "Customer data, contracts", "Need-to-know; encrypted when sent outside the company"],
          ["Restricted", "Salaries, security keys", "Named people only; never sent by email"]],
         [1.3 * inch, 2.2 * inch, 3.0 * inch]),
    PageBreak(),
    Paragraph("4. Reporting security incidents", H1),
    Paragraph("Report any suspected security incident, including phishing emails and lost devices, to the "
              "IT Service Desk within 1 hour of noticing it. Do not try to investigate an incident yourself.", BODY),
    Paragraph("5. Software", H1),
    Paragraph("Only software from the company software catalogue may be installed. Requests for new software "
              "are reviewed by the IT department within 5 working days.", BODY),
    Paragraph("6. Compliance", H1),
    Paragraph("Breaches of this policy may lead to disciplinary action. IT Security reviews this policy every "
              "12 months.", BODY),
]

out.mkdir(parents=True, exist_ok=True)
build("Leave_Policy.pdf", "Leave Policy - Brightwave Analytics", leave)
build("IT_Security_Policy.pdf", "IT Security Policy - Brightwave Analytics", security)
