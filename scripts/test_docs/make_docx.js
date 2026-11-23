// Generates the Word test documents for the KM demo.
// Usage: node make_docx.js <output_dir>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, LevelFormat, AlignmentType, BorderStyle,
} = require("docx");

const outDir = process.argv[2];
const FONT = "Arial";

const styles = {
  default: { document: { run: { font: FONT, size: 22 } } },
  paragraphStyles: [
    { id: "Title", name: "Title", basedOn: "Normal", next: "Normal",
      run: { font: FONT, size: 40, bold: true },
      paragraph: { spacing: { before: 0, after: 120 }, keepNext: true } },
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 30, bold: true },
      paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 24, bold: true },
      paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
  ],
};

const numbering = {
  config: [{
    reference: "bullets",
    levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
  }],
};

const page = { size: { width: 12240, height: 15840 },
  margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } };

const title = (t) => new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun(t)] });
const meta = (t) => new Paragraph({ spacing: { after: 240 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "999999", space: 4 } },
  children: [new TextRun({ text: t, italics: true, color: "555555", size: 20 })] });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const p = (t) => new Paragraph({ spacing: { after: 120 }, children: [new TextRun(t)] });
const bullet = (t) => new Paragraph({ numbering: { reference: "bullets", level: 0 },
  spacing: { after: 60 }, children: [new TextRun(t)] });

function table(widths, header, rows) {
  const total = widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, i, head) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: "E7E6E6" } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: head })] })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, i, false)) })),
    ],
  });
}

// ---------- Expense Policy ----------
const expense = [
  title("Travel and Expense Policy"),
  meta("Brightwave Analytics (fictional company for testing) - Policy FIN-02 - Effective 1 January 2026 - Owner: Finance"),
  h1("1. Purpose"),
  p("This policy explains which business expenses Brightwave reimburses, the spending limits for each category, and who must approve an expense before it is incurred."),
  h1("2. Spending limits and approvals"),
  p("All limits are in US dollars and include tax. Amounts above a limit are not reimbursed unless the approver named below signed off before the expense was incurred."),
  table([2400, 3480, 3480],
    ["Category", "Limit", "Approval required"],
    [
      ["Meals", "$75 per person per day", "Line manager"],
      ["Hotel", "$250 per night", "Line manager"],
      ["Travel (flights, trains, car hire)", "Up to $1,500 per trip", "Line manager"],
      ["Travel (flights, trains, car hire)", "Over $1,500 per trip", "Vice President (VP), before booking"],
      ["Software subscriptions", "Up to $100 per month", "None"],
      ["Software subscriptions", "Over $100 per month", "IT department"],
      ["Client entertainment", "$150 per guest", "Department Director"],
    ]),
  p(""),
  h1("3. Submitting a claim"),
  bullet("Submit claims in the finance portal within 30 days of the expense date."),
  bullet("Attach an itemised receipt for every expense over $25."),
  bullet("Claims submitted more than 60 days after the expense date are rejected."),
  bullet("Approved claims are paid with the next monthly payroll."),
  h1("4. Non-reimbursable items"),
  bullet("Alcohol, except as part of approved client entertainment."),
  bullet("Traffic and parking fines."),
  bullet("Upgrades to business or first class, unless a flight is longer than 8 hours."),
  bullet("Personal entertainment such as in-flight films or hotel minibar items."),
  h1("5. Policy breaches"),
  p("An expense above its limit without the required approval is treated as a policy breach. Finance will reimburse only up to the limit, and repeated breaches are reported to the employee's Department Director."),
];

// ---------- Employee Handbook ----------
const handbook = [
  title("Employee Handbook"),
  meta("Brightwave Analytics (fictional company for testing) - Version 3.1 - Effective 1 January 2026 - Owner: People Team"),
  h1("1. Working hours"),
  p("The standard working day is 9:00 to 17:30 with a one-hour lunch break. Core hours are 10:00 to 16:00; meetings should be scheduled inside core hours."),
  h1("2. Hybrid working"),
  p("Employees work in the office at least 3 days per week and may work remotely for the remaining days. Tuesday and Thursday are team days, when everyone is expected in the office."),
  p("Working from another country requires written approval from the People Team and is limited to 20 working days per calendar year."),
  h1("3. Equipment"),
  bullet("Every employee receives a company laptop on their first day."),
  bullet("A one-time home-office allowance of $300 is paid after the probation period."),
  bullet("Lost or stolen equipment must be reported to the IT Service Desk within 24 hours."),
  h1("4. Probation and reviews"),
  p("New employees have a probation period of 6 months. Performance reviews take place twice a year, in June and December, and salary changes take effect on 1 January."),
  h1("5. Learning budget"),
  p("Each employee has a learning budget of $1,000 per calendar year for courses, books and conferences. Unused budget does not carry over to the next year."),
  h1("6. Related policies"),
  p("Leave entitlements are set out in the Leave Policy. Spending limits are set out in the Travel and Expense Policy. Password, device and data rules are set out in the IT Security Policy."),
];

async function save(children, name) {
  const doc = new Document({ styles, numbering, sections: [{ properties: { page }, children }] });
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(path.join(outDir, name), buf);
  console.log("wrote", name, buf.length, "bytes");
}

(async () => {
  await save(expense, "Travel_and_Expense_Policy.docx");
  await save(handbook, "Employee_Handbook.docx");
})();
