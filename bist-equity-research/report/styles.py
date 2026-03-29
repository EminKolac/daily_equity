"""PDF stylesheet — fonts, margins, colors for ReportLab."""

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.units import inch, mm

# Colors
PRIMARY = colors.HexColor("#1B3A5C")
SECONDARY = colors.HexColor("#2E86AB")
POSITIVE = colors.HexColor("#27AE60")
NEGATIVE = colors.HexColor("#E74C3C")
NEUTRAL = colors.HexColor("#95A5A6")
ACCENT = colors.HexColor("#F39C12")
LIGHT_BG = colors.HexColor("#F8F9FA")
TABLE_HEADER = colors.HexColor("#1B3A5C")
TABLE_ALT = colors.HexColor("#F2F6FA")
DARK_TEXT = colors.HexColor("#2C3E50")
WHITE = colors.white

# Page
PAGE_WIDTH = 595.27  # A4
PAGE_HEIGHT = 841.89
MARGIN = 50


def get_styles():
    """Return custom paragraph styles for the equity report."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=24,
        textColor=WHITE,
        alignment=TA_LEFT,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        fontName="Helvetica",
        fontSize=14,
        textColor=colors.HexColor("#D4E6F1"),
        alignment=TA_LEFT,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=PRIMARY,
        spaceBefore=16,
        spaceAfter=8,
        borderWidth=0,
        borderPadding=0,
    ))

    styles.add(ParagraphStyle(
        name="SubSectionHeader",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="BodyText2",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK_TEXT,
        alignment=TA_JUSTIFY,
        spaceBefore=2,
        spaceAfter=4,
        leading=13,
    ))

    styles.add(ParagraphStyle(
        name="SmallText",
        fontName="Helvetica",
        fontSize=7,
        textColor=NEUTRAL,
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name="MetricLabel",
        fontName="Helvetica",
        fontSize=8,
        textColor=NEUTRAL,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="MetricValue",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=PRIMARY,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="RecommendationBox",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=WHITE,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="Disclaimer",
        fontName="Helvetica",
        fontSize=7,
        textColor=NEUTRAL,
        alignment=TA_JUSTIFY,
        leading=9,
    ))

    styles.add(ParagraphStyle(
        name="Footer",
        fontName="Helvetica",
        fontSize=7,
        textColor=NEUTRAL,
        alignment=TA_CENTER,
    ))

    return styles
