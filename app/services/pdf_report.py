"""Build the patient analysis PDF for the report blueprint.

Produces a real ``.pdf`` (not an HTML print page) using ReportLab. Designed
to look like a clinical report:

- Branded cover page with the patient name, report id, generated_at, and the
  clinician who triggered the download.
- A natively drawn (not embedded) semicircular risk gauge, color-coded to
  the risk band, with a needle pointing at the predicted probability.
- A feature table with traffic-light coloring (the same thresholds the HTML
  report view uses: ``cholesterol > 240``, ``restingbp > 140``,
  ``oldpeak > 1.5``).
- Top SHAP contributors (when available) listed with direction.
- Footer on every page: "Page N of M" + the educational disclaimer.

Color palette matches the project's CSS-variable palette (the rest of the
app, not the brighter inline hex the HTML report page uses):

    --primary   #2563eb
    --success   #16a34a
    --warning   #d97706
    --danger    #dc2626
    --muted     #64748b
    --text      #0f172a
    --border    #e2e8f0
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, Line, String, Wedge
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

log = logging.getLogger(__name__)


# --- Palette (matches app/static/css/app.css custom properties) -------------

PRIMARY = HexColor("#2563eb")
PRIMARY_DARK = HexColor("#1d4ed8")
SUCCESS = HexColor("#16a34a")
WARNING = HexColor("#d97706")
DANGER = HexColor("#dc2626")
MUTED = HexColor("#64748b")
TEXT = HexColor("#0f172a")
BORDER = HexColor("#e2e8f0")
SURFACE = HexColor("#ffffff")
PAGE_BG = HexColor("#f8fafc")

# Risk band thresholds — duplicated from app/predict.py so we never go stale
# silently; if the predict module changes its banding, update both.
RISK_LOW_MAX = 30.0
RISK_MODERATE_MAX = 60.0

# Healthy-range thresholds — duplicated from the HTML report view
# (app/templates/report/view_report.html) so the PDF and the HTML agree.
# Values are (desirable, upper_bound). Lower values are not flagged.
HEALTHY = {
    "Cholesterol": (200.0, 240.0),
    "RestingBP": (90.0, 140.0),
    "MaxHR": (60.0, 200.0),
    "Oldpeak": (0.0, 1.5),
}


# --- Styles -------------------------------------------------------------------


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=PRIMARY,
            alignment=0,  # left
            spaceAfter=8,
        ),
        "CoverSubtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=18,
            textColor=MUTED,
            spaceAfter=8,
        ),
        "CoverMeta": ParagraphStyle(
            "CoverMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT,
            spaceAfter=2,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=TEXT,
            spaceBefore=8,
            spaceAfter=8,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT,
            spaceAfter=6,
        ),
        "Caption": ParagraphStyle(
            "Caption",
            parent=base["Italic"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            alignment=0,
        ),
        "FooterText": ParagraphStyle(
            "FooterText",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
        "Disclaimer": ParagraphStyle(
            "Disclaimer",
            parent=base["Italic"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
        "DisclaimerCenter": ParagraphStyle(
            "DisclaimerCenter",
            parent=base["Italic"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            alignment=1,  # center
        ),
    }


# --- Helpers ------------------------------------------------------------------


def _risk_color(risk: str) -> HexColor:
    r = (risk or "").strip().lower()
    if r == "low":
        return SUCCESS
    if r == "moderate":
        return WARNING
    if r == "high":
        return DANGER
    return MUTED


def _health_color(metric: str, value: float) -> HexColor:
    """Return a traffic-light color for a single feature value, using the same
    thresholds the HTML report view applies. Only the *upper* bound is
    considered clinically meaningful — low cholesterol / low BP / low HR are
    not flagged here, matching the HTML view.
    """
    rng = HEALTHY.get(metric)
    if rng is None or value is None:
        return TEXT
    _low, high = rng
    if value > high:
        return DANGER
    margin = max(0.1 * high, 0.5)
    if value > (high - margin):
        return WARNING
    return SUCCESS


def _format_metric_value(metric: str, value: Any) -> str:
    if value is None:
        return "—"
    if metric in {"Cholesterol", "RestingBP", "MaxHR"}:
        return f"{float(value):.0f}"
    if metric == "Oldpeak":
        return f"{float(value):.1f}"
    if metric == "Age":
        return f"{float(value):.0f}"
    return str(value)


def _pretty_feature_name(raw_name: str) -> str:
    """Turn a SHAP preprocessing key like ``num__Cholesterol`` into
    ``Cholesterol`` (or ``ChestPainType: ATA`` for one-hot encoded categoricals).
    """
    if "__" in raw_name:
        prefix, rest = raw_name.split("__", 1)
        if prefix == "cat" and "_" in rest:
            col, _, value = rest.partition("_")
            return f"{col}: {value}"
        return rest
    return raw_name


def _top_shap(explanations: dict[str, float] | None, n: int = 5) -> list[tuple[str, float]]:
    if not explanations:
        return []
    items = [(k, float(v)) for k, v in explanations.items()]
    items.sort(key=lambda kv: abs(kv[1]), reverse=True)
    return items[:n]


def _pdf_gauge_drawing(probability: float, risk: str, width: float = 4.0 * 72,
                       height: float = 2.4 * 72) -> Drawing:
    """Build a ReportLab Drawing of a semicircular risk gauge.

    The gauge is drawn with native ReportLab shapes (lines, wedges, strings),
    so the output is vector and scales cleanly. ``probability`` is 0–100.
    """
    d = Drawing(width, height)
    cx = width / 2
    cy = height * 0.55  # gauge center; lower than vertical center to leave room for label
    radius = min(width, height * 1.7) * 0.42

    # Draw the three colored arcs (270° span).
    # Wedge angles in ReportLab are measured CCW from the +x axis.
    # We draw our gauge from the lower-left (start=135°) sweeping CCW back
    # across the top to the lower-right (end=45°, extent=270°).
    span = 270.0
    start_angle = 135.0

    low_end = (RISK_LOW_MAX / 100.0) * span
    mod_end = (RISK_MODERATE_MAX / 100.0) * span

    d.add(Wedge(
        cx, cy, radius,
        startangledegrees=start_angle,
        endangledegrees=start_angle + low_end,
        fillColor=SUCCESS,
        strokeColor=None,
    ))
    d.add(Wedge(
        cx, cy, radius,
        startangledegrees=start_angle + low_end,
        endangledegrees=start_angle + mod_end,
        fillColor=WARNING,
        strokeColor=None,
    ))
    d.add(Wedge(
        cx, cy, radius,
        startangledegrees=start_angle + mod_end,
        endangledegrees=start_angle + span,
        fillColor=DANGER,
        strokeColor=None,
    ))

    # Needle: rotate from "start_angle" sweeping back CCW with probability.
    needle_angle_deg = start_angle - (probability / 100.0) * span
    needle_angle_rad = math.radians(needle_angle_deg)
    nx = cx + radius * math.cos(needle_angle_rad)
    ny = cy + radius * math.sin(needle_angle_rad)

    d.add(Line(cx, cy, nx, ny, strokeColor=TEXT, strokeWidth=2.5,
               strokeLineCap=1))
    d.add(Circle(cx, cy, 5, fillColor=TEXT, strokeColor=None))

    # Value label below the gauge.
    label_color = _risk_color(risk)
    label = String(
        cx,
        height * 0.10,
        f"{probability:.1f}%  ·  {risk}",
        fontName="Helvetica-Bold",
        fontSize=14,
        fillColor=label_color,
        textAnchor="middle",
    )
    d.add(label)

    # Scale labels at the segment boundaries.
    for pct, txt in ((0, "0"), (RISK_LOW_MAX, f"{RISK_LOW_MAX:.0f}"),
                     (RISK_MODERATE_MAX, f"{RISK_MODERATE_MAX:.0f}"), (100, "100")):
        ang = math.radians(start_angle - (pct / 100.0) * span)
        lx = cx + (radius + 12) * math.cos(ang)
        ly = cy + (radius + 12) * math.sin(ang)
        d.add(String(lx, ly - 4, txt, fontName="Helvetica", fontSize=8,
                     fillColor=MUTED, textAnchor="middle"))

    return d


# --- Page callbacks -----------------------------------------------------------


class _PdfDoc(BaseDocTemplate):
    """Custom doc that tracks total page count for the footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_count = 0

    def afterPage(self) -> None:
        self._page_count += 1


def _draw_footer(canvas, doc: _PdfDoc) -> None:
    """Draw the per-page footer. Called by the onPage PageTemplate hook."""
    canvas.saveState()
    page_w, page_h = doc.pagesize
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)

    # Left: disclaimer
    canvas.drawString(
        doc.leftMargin,
        0.45 * inch,
        "",
    )

    # Right: page N of M
    canvas.drawRightString(
        page_w - doc.rightMargin,
        0.45 * inch,
        f"Page {doc.page} of {doc._page_count}",
    )
    canvas.restoreState()


def _draw_cover_chrome(canvas, doc: _PdfDoc) -> None:
    """Draw a colored brand bar across the top of the cover page only."""
    canvas.saveState()
    page_w, _ = doc.pagesize
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, doc.pagesize[1] - 0.35 * inch, page_w, 0.35 * inch,
                stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(doc.leftMargin, doc.pagesize[1] - 0.24 * inch,
                      "CorAi · Heart Risk Assessment")
    canvas.restoreState()


# --- Public API ---------------------------------------------------------------


def build_patient_pdf(
    report: Any,
    patient: Any,
    prediction: Any,
    explanations: dict[str, float] | None = None,
    generated_by: Any = None,
) -> bytes:
    """Build the patient-analysis PDF and return its raw bytes.

    ``report`` is a ``PdfReport`` row, ``patient`` a ``Patient`` row,
    ``prediction`` a ``Prediction`` row, ``explanations`` a dict from
    ``Predictor.explain()`` (or None), ``generated_by`` a ``User`` row
    (or None — the function tolerates anonymous callers).
    """

    import io

    buffer = io.BytesIO()
    doc = _PdfDoc(
        buffer,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title="CorAi Patient Analysis Report",
        author="CorAi",
        subject=f"Patient Analysis Report #{getattr(report, 'id', '')}",
    )

    cover_frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="cover",
        showBoundary=0,
    )
    body_frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="body",
        showBoundary=0,
    )

    cover_template = PageTemplate(
        id="Cover",
        frames=[cover_frame],
        onPage=_draw_cover_chrome,
    )
    body_template = PageTemplate(
        id="Body",
        frames=[body_frame],
        onPage=_draw_footer,
    )

    doc.addPageTemplates([cover_template, body_template])

    styles = _build_styles()
    story = _build_story(report, patient, prediction, explanations,
                         generated_by, styles)

    try:
        doc.build(story)
    except Exception:
        log.exception("Failed to build PDF for report %s", getattr(report, "id", "?"))
        raise

    buffer.seek(0)
    return buffer.getvalue()


def _build_story(report, patient, prediction, explanations, generated_by,
                  styles) -> list:
    story: list = []

    # --- Cover page ---------------------------------------------------------
    story.append(Spacer(1, 1.0 * inch))
    story.append(Paragraph("Cardiovascular Health Report", styles["CoverTitle"]))
    story.append(Paragraph(
        "Patient analysis generated by the CorAi.",
        styles["CoverSubtitle"],
    ))
    story.append(Spacer(1, 0.5 * inch))

    patient_name = (
        getattr(patient, "name", None)
        or getattr(report, "patient_name", None)
        or "Anonymous"
    )

    cover_rows = [
        ("Patient", patient_name),
        ("Report ID", f"#{getattr(report, 'id', '')}"),
        ("Generated",
         datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")),
    ]
    if generated_by is not None:
        role = getattr(generated_by, "role", "")
        cover_rows.append(
            ("Clinician",
             f"{getattr(generated_by, 'username', '')}"
             + (f"  ({role})" if role else "")),
        )
    if getattr(report, "address", None):
        cover_rows.append(("Location", report.address))

    cover_table = Table(
        [[Paragraph(k, styles["Body"]), Paragraph(v, styles["Body"])]
         for k, v in cover_rows],
        colWidths=[1.4 * inch, 4.6 * inch],
    )
    cover_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, BORDER),
    ]))
    story.append(cover_table)

    story.append(Spacer(1, 1.0 * inch))
    # Educational disclaimer removed per requirement)

    story.append(PageBreak())

    # --- Page 2: Risk summary + gauge --------------------------------------
    story.append(Paragraph("Risk summary", styles["SectionHeading"]))

    probability = float(getattr(prediction, "probability", 0.0) or 0.0)
    risk = str(getattr(prediction, "risk", "Unknown"))

    gauge = _pdf_gauge_drawing(probability, risk)
    story.append(gauge)
    story.append(Spacer(1, 0.2 * inch))

    if risk == "Low":
        advice = (
            "Cardiac metrics are within or close to healthy baseline limits. "
            "Maintain a balanced diet, keep active, and schedule regular "
            "checkups."
        )
    elif risk == "Moderate":
        advice = (
            "Elevated cardiovascular risk parameters detected. Consider "
            "sharing this report with your physician and reviewing your "
            "lifestyle habits (diet, exercise, sleep, stress)."
        )
    else:
        advice = (
            "High-risk indicators observed. We strongly advise scheduling "
            "a consultation with a cardiologist to review these metrics "
            "immediately."
        )
    story.append(Paragraph(advice, styles["Body"]))

    story.append(Spacer(1, 0.2 * inch))

    # --- Feature table ------------------------------------------------------
    story.append(Paragraph("Extracted patient metrics", styles["SectionHeading"]))

    features_data = [
        ["Metric", "Value", "Healthy range", "Status"],
        ["Age", _format_metric_value("Age", patient.age), "—", "—"],
        ["Sex", "Male" if patient.sex == "M" else "Female", "—", "—"],
        ["Chest pain type", _cp_label(patient.cp), "—", "—"],
        ["Resting BP", f"{_format_metric_value('RestingBP', patient.restingbp)} mmHg",
         "≤ 140", _status_for("RestingBP", patient.restingbp)],
        ["Cholesterol", f"{_format_metric_value('Cholesterol', patient.cholesterol)} mg/dL",
         "≤ 240", _status_for("Cholesterol", patient.cholesterol)],
        ["Fasting blood sugar > 120", "Yes" if int(patient.fastingbs or 0) == 1 else "No",
         "No", "—"],
        ["Resting ECG", patient.restecg or "—", "—", "—"],
        ["Max heart rate", f"{_format_metric_value('MaxHR', patient.maxhr)} bpm",
         "60 – 200", _status_for("MaxHR", patient.maxhr)],
        ["Exercise-induced angina", "Yes" if patient.exang == "Y" else "No",
         "No", "—"],
        ["ST depression (Oldpeak)", _format_metric_value("Oldpeak", patient.oldpeak),
         "≤ 1.5", _status_for("Oldpeak", patient.oldpeak)],
        ["ST slope", patient.slope or "—", "—", "—"],
    ]

    feature_table = Table(features_data, colWidths=[1.7 * inch, 1.3 * inch,
                                                    1.4 * inch, 1.1 * inch])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), PAGE_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
    ]
    # Color the "Status" cell for numeric metrics that have a known healthy range.
    health_metric_to_row = {
        "RestingBP": 4,
        "Cholesterol": 5,
        "MaxHR": 8,
        "Oldpeak": 10,
    }
    for metric, row_idx in health_metric_to_row.items():
        value = getattr(patient, metric.lower() if metric != "MaxHR" else "maxhr", None)
        # Special-case maxhr attribute access.
        if metric == "MaxHR":
            value = patient.maxhr
        else:
            value = getattr(patient, metric.lower(), None)
        color = _health_color(metric, value)
        style_cmds.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), color))
        style_cmds.append(("FONTNAME", (3, row_idx), (3, row_idx), "Helvetica-Bold"))
    feature_table.setStyle(TableStyle(style_cmds))
    story.append(feature_table)


    # --- Provenance footer block -------------------------------------------
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        f"Model version: {getattr(prediction, 'model_version', 'unknown')}.",
        styles["Caption"],
    ))

    return story


def _cp_label(cp: str | None) -> str:
    mapping = {
        "TA": "Typical angina (TA)",
        "ATA": "Atypical angina (ATA)",
        "NAP": "Non-anginal pain (NAP)",
        "ASY": "Asymptomatic (ASY)",
    }
    return mapping.get((cp or "").upper(), cp or "—")


def _status_for(metric: str, value: Any) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    color = _health_color(metric, v)
    if color is DANGER:
        return "Out of range"
    if color is WARNING:
        return "Borderline"
    return "OK"
