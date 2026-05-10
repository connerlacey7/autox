import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, PageBreak

ORANGE       = colors.HexColor('#E8820C')
GRAY         = colors.HexColor('#808080')
GREEN        = colors.HexColor('#92D050')
ROW_ALT      = colors.HexColor('#F2F2F2')
WHITE        = colors.white
BLACK        = colors.black
LIGHT_BORDER = colors.HexColor('#CCCCCC')

# Approximate row height in points (font 6.5 + 2pt padding top + 2pt bottom)
ROW_H = 14
# Portrait has ~742pt usable height; title ~70pt leaves ~672pt → ~48 rows.
# Use 44 to be safe across all pages.
ROWS_PER_CHUNK = 44


def _make_style(header_bg, header_text=WHITE):
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR',     (0, 0), (-1, 0), header_text),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 6.5),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('GRID',          (0, 0), (-1, -1), 0.25, LIGHT_BORDER),
        ('ALIGN',         (-1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN',         (-2, 0), (-2, -1), 'RIGHT'),
    ])


def _make_class_style():
    s = _make_style(GRAY)
    s.add('SPAN',      (0, 0), (1, 0))
    s.add('FONTNAME',  (0, 1), (0, -1), 'Helvetica-Bold')
    s.add('TEXTCOLOR', (0, 1), (0, -1), GRAY)
    s.add('ALIGN',     (2, 0), (2, -1), 'RIGHT')
    s.add('ALIGN',     (3, 0), (3, -1), 'RIGHT')
    return s


def _make_part_style():
    s = _make_style(GREEN, BLACK)
    s.add('ALIGN', (1, 0), (1, -1), 'RIGHT')
    return s


def _outer_table(pax_t, raw_t, class_t, part_t, pax_cw, raw_cw, class_cw, part_cw):
    gap = 0.08 * inch
    t = Table(
        [[pax_t, raw_t, class_t, part_t]],
        colWidths=[sum(pax_cw)+gap, sum(raw_cw)+gap, sum(class_cw)+gap, sum(part_cw)],
        hAlign='LEFT',
    )
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def build_season_pdf(season_year, events_completed, pax_rows, raw_rows,
                     class_rows, participants) -> bytes:
    buffer = io.BytesIO()
    margin = 0.35 * inch
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )

    # Portrait usable width ~7.80in; total below = 7.70in leaving slight slack
    pax_cw   = [0.20*inch, 1.20*inch, 0.48*inch, 0.20*inch]
    raw_cw   = [0.20*inch, 1.20*inch, 0.48*inch, 0.20*inch]
    class_cw = [0.36*inch, 1.10*inch, 0.22*inch, 0.28*inch]
    part_cw  = [1.10*inch, 0.24*inch]

    # ── Build full data rows (no header) ─────────────────────────────────────
    pax_hdr   = [['', 'PAX RESULTS', 'Pax Pts', 'Ev']]
    raw_hdr   = [['', 'RAW RESULTS', 'Raw Pts', 'Ev']]
    class_hdr = [['CLASS RESULTS', '', 'Ev', 'Pts']]
    part_hdr  = [['All Participants', 'Ev']]

    pax_body = []
    for i, r in enumerate(pax_rows, 1):
        pax_body.append([str(i), f"{r['first_name']} {r['last_name']}",
                         f"{float(r['total_pax_points']):.2f}", str(r['events_counted'])])

    raw_body = []
    for i, r in enumerate(raw_rows, 1):
        raw_body.append([str(i), f"{r['first_name']} {r['last_name']}",
                         f"{float(r['total_raw_points']):.2f}", str(r['events_counted'])])

    class_body = []
    current_class = None
    for r in class_rows:
        cls_label = r['class'] if r['class'] != current_class else ''
        current_class = r['class']
        class_body.append([cls_label, f"{r['first_name']} {r['last_name']}",
                           str(r['events_counted']), str(int(r['total_points']))])

    part_body = []
    for r in participants:
        part_body.append([f"{r['first_name']} {r['last_name']}", str(r['events_attended'])])

    max_rows = max(len(pax_body), len(raw_body), len(class_body), len(part_body))

    # ── Header styles ─────────────────────────────────────────────────────────
    title_style = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=18,
                                  alignment=TA_CENTER, spaceAfter=1, leading=20)
    sub_style   = ParagraphStyle('S', fontName='Helvetica-Bold', fontSize=11,
                                  alignment=TA_CENTER, spaceAfter=2, leading=13)
    ev_style    = ParagraphStyle('E', fontName='Helvetica', fontSize=7,
                                  alignment=TA_LEFT, spaceAfter=6, textColor=GRAY, leading=9)

    events_str = ', '.join(str(e) for e in events_completed)

    story = [
        Paragraph(f"{season_year} SEASON", title_style),
        Paragraph("AUTOCROSS RESULTS", sub_style),
        Paragraph(f"Events Completed: {events_str}", ev_style),
    ]

    # ── Paginate: one outer table per chunk ───────────────────────────────────
    for page_num, start in enumerate(range(0, max(max_rows, 1), ROWS_PER_CHUNK)):
        end = start + ROWS_PER_CHUNK

        def chunk(body, hdr):
            return hdr + body[start:end] if body[start:end] else hdr + [['', '', '', '']]

        pax_chunk   = pax_hdr   + pax_body[start:end]   or pax_hdr   + [['','','','']]
        raw_chunk   = raw_hdr   + raw_body[start:end]   or raw_hdr   + [['','','','']]
        class_chunk = class_hdr + class_body[start:end] or class_hdr + [['','','','']]
        part_chunk  = part_hdr  + part_body[start:end]  or part_hdr  + [['','']]

        def row_heights(chunk):
            return [13] + [11] * (len(chunk) - 1)

        pax_t = Table(pax_chunk, colWidths=pax_cw, rowHeights=row_heights(pax_chunk))
        pax_t.setStyle(_make_style(ORANGE))

        raw_t = Table(raw_chunk, colWidths=raw_cw, rowHeights=row_heights(raw_chunk))
        raw_t.setStyle(_make_style(ORANGE))

        class_t = Table(class_chunk, colWidths=class_cw, rowHeights=row_heights(class_chunk))
        class_t.setStyle(_make_class_style())

        part_t = Table(part_chunk, colWidths=part_cw, rowHeights=row_heights(part_chunk))
        part_t.setStyle(_make_part_style())

        story.append(_outer_table(pax_t, raw_t, class_t, part_t,
                                   pax_cw, raw_cw, class_cw, part_cw))

        if end < max_rows:
            story.append(PageBreak())
            story.append(Paragraph(f"{season_year} SEASON (continued)", title_style))
            story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
