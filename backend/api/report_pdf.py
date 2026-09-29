"""PDF rendering helpers for repository analysis reports."""
import re
from collections import Counter
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#657086")
ACCENT = colors.HexColor("#5557C9")
PALE = colors.HexColor("#F2F3FA")
LINE = colors.HexColor("#DCE0EA")
SEVERITY_COLORS = {
    "high": colors.HexColor("#B42318"),
    "medium": colors.HexColor("#B54708"),
    "low": colors.HexColor("#475467"),
}


def _text(value) -> str:
    """Make arbitrary repository or model text safe for ReportLab's fonts/XML."""
    value = str("" if value is None else value).replace("\x00", "")
    return value.encode("cp1252", errors="replace").decode("cp1252")


def _inline_markup(value: str) -> str:
    """Escape text, then support the small set of inline Markdown used in guides."""
    result = escape(_text(value))
    result = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda match: f'<link href="{match.group(2)}" color="{ACCENT.hexval()}">{match.group(1)}</link>',
        result,
    )
    result = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', result)
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    result = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", result)
    return result


def _guide_flowables(markdown: str, styles: dict) -> list:
    """Render common Markdown guide blocks as paginated ReportLab flowables."""
    flowables = []
    paragraph_lines = []
    code_lines = []
    in_code = False

    def flush_paragraph():
        if paragraph_lines:
            flowables.append(Paragraph(_inline_markup(" ".join(paragraph_lines)), styles["body"]))
            flowables.append(Spacer(1, 3))
            paragraph_lines.clear()

    for raw_line in _text(markdown).splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            flush_paragraph()
            if in_code:
                code = "\n".join(code_lines)
                if code.strip():
                    flowables.append(Preformatted(escape(code), styles["code"], maxLineLength=92))
                    flowables.append(Spacer(1, 5))
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if re.fullmatch(r"(?:[-*_]\s*){3,}", stripped):
            flush_paragraph()
            flowables.append(HRFlowable(width="100%", color=LINE, thickness=0.6, spaceAfter=7))
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            style_name = "guide_h1" if len(heading.group(1)) <= 2 else "guide_h2"
            flowables.append(Paragraph(_inline_markup(heading.group(2)), styles[style_name]))
            continue
        bullet = re.match(r"^\s*[-+*]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            flowables.append(Paragraph("&#8226; " + _inline_markup(bullet.group(1)), styles["list"]))
            continue
        numbered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if numbered:
            flush_paragraph()
            number = re.match(r"^\s*(\d+)[.)]", line).group(1)
            flowables.append(Paragraph(f"{number}. " + _inline_markup(numbered.group(1)), styles["list"]))
            continue
        if stripped.startswith("> "):
            flush_paragraph()
            flowables.append(Paragraph(_inline_markup(stripped[2:]), styles["quote"]))
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            # Keep guide tables readable without requiring an extra Markdown package.
            flush_paragraph()
            if re.fullmatch(r"\|?[-: |]+\|?", stripped):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            flowables.append(Paragraph(" &nbsp; | &nbsp; ".join(_inline_markup(cell) for cell in cells), styles["body"]))
            continue
        paragraph_lines.append(stripped)

    flush_paragraph()
    if code_lines:
        flowables.append(Preformatted(escape("\n".join(code_lines)), styles["code"], maxLineLength=92))
    return flowables


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="report_title", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=23, leading=28, textColor=INK, alignment=TA_CENTER, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="repo_name", parent=styles["Normal"], fontName="Helvetica",
        fontSize=11, leading=15, textColor=MUTED, alignment=TA_CENTER, spaceAfter=13,
    ))
    styles.add(ParagraphStyle(
        name="section", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, leading=18, textColor=INK, spaceBefore=15, spaceAfter=7,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="subsection", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=10, leading=13, textColor=INK, spaceBefore=8, spaceAfter=3,
        keepWithNext=True, splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="body", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.7, leading=12.2, textColor=INK, spaceAfter=3,
        splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="small", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8, leading=10.5, textColor=MUTED, splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="list", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.7, leading=12, textColor=INK, leftIndent=10, firstLineIndent=-8,
        spaceAfter=2, splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="quote", parent=styles["BodyText"], fontName="Helvetica-Oblique",
        fontSize=8.5, leading=12, textColor=MUTED, leftIndent=12, borderColor=LINE,
        borderWidth=0, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="code", fontName="Courier", fontSize=7.2, leading=9.2,
        textColor=INK, backColor=PALE, borderColor=LINE, borderWidth=0.4,
        borderPadding=6, leftIndent=5, rightIndent=5, spaceBefore=3, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="guide_h1", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=14, textColor=ACCENT, spaceBefore=9, spaceAfter=4,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="guide_h2", parent=styles["Heading4"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=INK, spaceBefore=6, spaceAfter=3,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="table", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.3, leading=11, textColor=INK, splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="table_label", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=MUTED,
    ))
    return styles


def _paragraph(value, style):
    return Paragraph(_inline_markup(value), style)


def _draw_page(canvas, document):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(document.leftMargin, 15 * mm, width - document.rightMargin, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, 10 * mm, "Generated by RepoRadar")
    canvas.drawRightString(width - document.rightMargin, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def build_repository_report(repository) -> bytes:
    """Return a complete PDF report for a saved repository analysis."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=21 * mm,
        title=f"RepoRadar report - {repository.owner}/{repository.name}",
        author="RepoRadar",
    )
    styles = _styles()
    story = [
        Spacer(1, 5 * mm),
        Paragraph("Repository Analysis Report", styles["report_title"]),
        Paragraph(_inline_markup(f"{repository.owner}/{repository.name}"), styles["repo_name"]),
        HRFlowable(width="100%", color=ACCENT, thickness=1.4, spaceAfter=8),
    ]

    story.append(Paragraph("Repository", styles["section"]))
    analyzed_at = "Not available"
    if repository.analyzed_at:
        analyzed_at = timezone.localtime(repository.analyzed_at).strftime("%Y-%m-%d %H:%M %Z")
    metadata = [
        ("GitHub URL", repository.url),
        ("Description", repository.description or "No description provided."),
        ("Primary language", repository.language or "Unknown"),
        ("Default branch", repository.default_branch or "Unknown"),
        ("Stars", f"{repository.stars:,}"),
        ("Analyzed", analyzed_at),
    ]
    metadata_rows = [
        [_paragraph(label, styles["table_label"]), _paragraph(value, styles["table"])]
        for label, value in metadata
    ]
    metadata_table = Table(metadata_rows, colWidths=[34 * mm, 140 * mm], hAlign="LEFT")
    metadata_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([metadata_table, Spacer(1, 4)])

    stats = repository.stats if isinstance(repository.stats, dict) else {}
    graph = repository.graph_data if isinstance(repository.graph_data, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    smells = repository.smells if isinstance(repository.smells, list) else []
    smells = [smell for smell in smells if isinstance(smell, dict)]
    severity_counts = Counter(str(smell.get("severity", "low")).lower() for smell in smells)

    story.append(Paragraph("Analysis Summary", styles["section"]))
    metrics = [
        ("Files", stats.get("file_count", 0)),
        ("Modules", stats.get("module_count", 0)),
        ("Classes", stats.get("class_count", 0)),
        ("Functions", stats.get("function_count", 0)),
        ("Graph nodes", len(nodes)),
        ("Graph edges", len(edges)),
        ("Code smells", len(smells)),
        ("Unparsed files", stats.get("unparsed_files", 0)),
    ]
    metric_rows = []
    for offset in range(0, len(metrics), 2):
        left = metrics[offset]
        right = metrics[offset + 1]
        metric_rows.append([
            _paragraph(left[0], styles["table_label"]), _paragraph(f"{left[1]:,}" if isinstance(left[1], int) else left[1], styles["table"]),
            _paragraph(right[0], styles["table_label"]), _paragraph(f"{right[1]:,}" if isinstance(right[1], int) else right[1], styles["table"]),
        ])
    metric_table = Table(metric_rows, colWidths=[43 * mm, 44 * mm, 43 * mm, 44 * mm], hAlign="LEFT")
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE),
        ("BACKGROUND", (2, 0), (2, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(metric_table)

    if stats.get("structure_overview"):
        story.append(Paragraph("Project Structure", styles["subsection"]))
        story.append(Paragraph(_inline_markup(stats["structure_overview"]), styles["body"]))

    languages = stats.get("top_languages") or {}
    if not isinstance(languages, dict):
        languages = {}
    if languages:
        story.append(Paragraph("Languages", styles["subsection"]))
        language_rows = [[
            _paragraph("Language", styles["table_label"]),
            _paragraph("Files", styles["table_label"]),
        ]]
        for language, count in languages.items():
            language_rows.append([_paragraph(language, styles["table"]), _paragraph(count, styles["table"])])
        language_table = Table(language_rows, colWidths=[140 * mm, 34 * mm], hAlign="LEFT")
        language_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PALE),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(language_table)

    story.append(Paragraph("Code Smells", styles["section"]))
    severity_line = "  |  ".join(
        f"{severity.title()}: {severity_counts.get(severity, 0)}"
        for severity in ("high", "medium", "low")
    )
    story.append(Paragraph(
        _inline_markup(f"{len(smells)} finding(s)  |  {severity_line}"), styles["body"]
    ))
    if not smells:
        story.append(Paragraph("No code smells were detected.", styles["body"]))
    else:
        for index, smell in enumerate(smells, start=1):
            severity = str(smell.get("severity", "low")).lower()
            severity_color = SEVERITY_COLORS.get(severity, MUTED)
            title = _inline_markup(smell.get("title") or "Code smell")
            label = escape(_text(severity.upper()))
            heading = Paragraph(
                f'<font color="{severity_color.hexval()}"><b>{label}</b></font>'
                f' &nbsp; {index}. {title}',
                styles["subsection"],
            )
            location = str(smell.get("file") or "")
            if smell.get("line") is not None:
                location += f":{smell['line']}"
            block = [heading]
            if location:
                block.append(Paragraph(
                    f'<font color="{MUTED.hexval()}">Location: '
                    f"{_inline_markup(location)}</font>",
                    styles["small"],
                ))
            for label, key in (("Detail", "detail"), ("Why it matters", "explanation"), ("Suggestion", "suggestion")):
                if smell.get(key):
                    block.append(Paragraph(f"<b>{label}:</b> {_inline_markup(smell[key])}", styles["body"]))
            block.append(Spacer(1, 4))
            story.append(KeepTogether(block))

    story.append(Paragraph("Onboarding Guide", styles["section"]))
    guide = _text(repository.guide_markdown or "").strip()
    if guide:
        story.extend(_guide_flowables(guide, styles))
    else:
        story.append(Paragraph("No onboarding guide was generated for this analysis.", styles["body"]))

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()
