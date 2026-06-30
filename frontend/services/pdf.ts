import jsPDF from "jspdf";

function formatDate(date: Date) {
  const day = date.getDate();
  const month = date.toLocaleString("en-US", { month: "long" });
  const year = date.getFullYear();
  let hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return `${day} ${month} ${year}, ${hours}:${minutes} ${ampm}`;
}

export function downloadPDF(
  overallScore: number,
  skills: any,
  experience: any,
  education: any,
  certifications: any,
  projects: any,
  suggestions: string[]
) {
  const doc = new jsPDF();
  const margin = 20;
  const pageW = 210;
  const contentW = pageW - margin * 2;
  let y = 20;

  // ── page break ───────────────────────────────────────────
  function checkPage(needed: number) {
    if (y + needed > 275) {
      doc.addPage();
      y = 20;
    }
  }

  // ── section heading + underline ──────────────────────────
  function sectionHeading(title: string) {
    checkPage(14);
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(30, 30, 30);
    doc.text(title, margin, y);
    y += 2;
    doc.setDrawColor(160, 160, 160);
    doc.setLineWidth(0.3);
    doc.line(margin, y, margin + contentW, y);
    y += 6;
  }

  // ── bordered list box ────────────────────────────────────
  // Collects all lines first, THEN draws the border around them
  function borderedList(items: string[]) {
    if (!items || items.length === 0) return;

    doc.setFontSize(9.5);
    doc.setFont("helvetica", "normal");

    // width of "  • " so wrapped lines align under the text, not the bullet
    const bulletIndent = doc.getTextWidth("  • ");

    type Line = { text: string; indent: number };
    const allLines: Line[] = [];

    items.forEach((item) => {
      const wrapped: string[] = doc.splitTextToSize(
        "  " + item,
        contentW - 10
      );
      wrapped.forEach((l, i) => {
        // strip the leading "  • " from continuation lines if splitTextToSize re-adds spacing
        allLines.push({ text: l, indent: i === 0 ? 0 : bulletIndent });
      });
    });
  
    const lineH = 6.5;
    const padTop = 5;
    const padBot = 4;
    const boxH = padTop + allLines.length * lineH + padBot;

    // if the whole box doesn't fit, move to next page
    checkPage(boxH + 2);

    const boxY = y;

    // draw border first (now we know total height)
    doc.setDrawColor(180, 180, 180);
    doc.setLineWidth(0.4);
    doc.rect(margin, boxY, contentW, boxH);

    // draw text inside
    doc.setFontSize(9.5);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(50, 50, 50);

    let ty = boxY + padTop + 3.5; // baseline of first line
    allLines.forEach((line) => {
      doc.text(line.text, margin + 5 + line.indent, ty);
      ty += lineH;
    });

    y = boxY + boxH + 6;
  }

  // ════════════════════════════════════════════════════════
  // TITLE
  // ════════════════════════════════════════════════════════

  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(20, 20, 20);
  doc.text("ATS Resume Analysis Report", margin, y);
  y += 4;
  doc.setDrawColor(60, 60, 60);
  doc.setLineWidth(0.6);
  doc.line(margin, y, margin + contentW, y);
  y += 10;

  // ════════════════════════════════════════════════════════
  // OVERALL SCORE BOX
  // ════════════════════════════════════════════════════════

  const scoreBoxH = 18;
  doc.setDrawColor(180, 180, 180);
  doc.setLineWidth(0.4);
  doc.rect(margin, y, contentW, scoreBoxH);

  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(30, 30, 30);
  doc.text("Overall ATS Score", margin + 4, y + 7);

  doc.setFontSize(13);
  doc.text(`${Math.round(overallScore)}%`, margin + contentW - 4, y + 7, { align: "right" });

  doc.setFontSize(8.5);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(90, 90, 90);
  doc.text(`Generated: ${formatDate(new Date())}`, margin + 4, y + 14);

  y += scoreBoxH + 10;

  // ════════════════════════════════════════════════════════
  // SCORE SUMMARY
  // ════════════════════════════════════════════════════════

  sectionHeading("Score Summary");

  const scores = [
    { label: "Skills", val: skills?.score ?? 0 },
    { label: "Experience", val: experience?.score ?? 0 },
    { label: "Projects", val: projects?.score ?? 0 },
    { label: "Education", val: education?.score ?? 0 },
    { label: "Certifications", val: certifications?.score ?? 0 },
  ];

  const rowH = 9;
  const padTop = 3;
  const tableH = padTop + scores.length * rowH + 3;

  checkPage(tableH + 2);
  const tableY = y;

  doc.setDrawColor(180, 180, 180);
  doc.setLineWidth(0.4);
  doc.rect(margin, tableY, contentW, tableH);

  scores.forEach((s, i) => {
    const rowY = tableY + padTop + i * rowH;
    doc.setFontSize(9.5);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(50, 50, 50);
    doc.text(s.label, margin + 5, rowY + 6);
    doc.setFont("helvetica", "bold");
    doc.text(`${Math.round(s.val)}%`, margin + contentW - 5, rowY + 6, { align: "right" });

    if (i < scores.length - 1) {
      doc.setDrawColor(220, 220, 220);
      doc.setLineWidth(0.2);
      doc.line(margin + 3, rowY + rowH, margin + contentW - 3, rowY + rowH);
    }
  });

  y = tableY + tableH + 8;

  // ════════════════════════════════════════════════════════
  // SKILLS SECTIONS
  // ════════════════════════════════════════════════════════

  const matched: string[] = skills?.matched ?? [];
  const missing: string[] = skills?.missing ?? [];
  const inferred: string[] = skills?.inferred ?? [];

  if (matched.length > 0) {
    sectionHeading(`Matched Skills  (${matched.length})`);
    borderedList(matched.map((i) => "• " + i));
  }

  if (missing.length > 0) {
    sectionHeading(`Missing Skills  (${missing.length})`);
    borderedList(missing.map((i) => "• " + i));
  }

  if (inferred.length > 0) {
    sectionHeading(`Inferred Skills  (${inferred.length})`);
    borderedList(inferred.map((i) => "• " + i));
  }

  // ════════════════════════════════════════════════════════
  // SUGGESTIONS
  // ════════════════════════════════════════════════════════

  if (suggestions && suggestions.length > 0) {
    sectionHeading("Suggestions");
    borderedList(suggestions.map((i) => "• " + i));
  }

  doc.save("ATS_Report.pdf");
}