"""PDF builder for the Temettü & Sermaye (Dividend & Capital) dashboard.

Mirrors the Power BI layout supplied by the user:

* Header strip with Ticker / Year slicer indicators.
* Four KPI cards (Brüt Temettü TRY, Net Temettü TRY, Avg Yield, Avg Payout).
* Two-column chart row:
  - Horizontal stacked bar of gross + net dividend income by ticker.
  - Line chart of yearly average yield and payout.
* Detail table (Ticker, Year, DPS, Gross_Income_TRY, Net_Income_TRY,
  Yield, Payout_Ratio).
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from analysis.portfolio_dividends import DividendDashboardData
from charts.dividend_dashboard_charts import (
    dividend_income_by_ticker_chart,
    portfolio_cost_basis_chart,
    yield_payout_trend_chart,
)
from charts.style import format_turkish_number
from config.portfolio import get_positions_df
from report.styles import (
    ACCENT,
    DARK_TEXT,
    LIGHT_BG,
    NEUTRAL,
    PRIMARY,
    SECONDARY,
    TABLE_ALT,
    TABLE_HEADER,
    WHITE,
    get_styles,
)

logger = logging.getLogger(__name__)


def _img_flowable(png: bytes, width: float, max_height: float) -> Image | None:
    if not png:
        return None
    buf = io.BytesIO(png)
    try:
        reader = ImageReader(buf)
        iw, ih = reader.getSize()
        aspect = ih / iw if iw else 1
        height = width * aspect
        if height > max_height:
            height = max_height
            width = height / aspect
        buf.seek(0)
        img = Image(buf, width=width, height=height)
        img.hAlign = "CENTER"
        return img
    except Exception:
        logger.warning("Dashboard chart image failed to decode (%d bytes)", len(png))
        return None


def _fmt_money_try(value: float) -> str:
    if value is None or pd.isna(value):
        return "—"
    if abs(value) >= 1e9:
        return f"{value / 1e9:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".") + "Mrd"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + "M"
    return format_turkish_number(value)


def _fmt_pct(value: float, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    # Value is expected as a ratio (0.029 -> 2,9%); if it already looks
    # like a percentage (>1) assume caller passed 2.9 already.
    pct = value * 100 if abs(value) <= 1 else value
    s = f"{pct:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"%{s}"


def _fmt_dps(value: float) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _slicer_box(label: str, value: str, styles: dict, width: float) -> Table:
    label_p = Paragraph(
        f"<font color='#7F8C8D' size='7'>{label.upper()}</font>",
        styles["SmallText"],
    )
    value_p = Paragraph(
        f"<font color='#1B3A5C' size='10'><b>{value}</b></font>",
        ParagraphStyle("slicer_val", fontName="Helvetica", fontSize=10,
                       textColor=DARK_TEXT),
    )
    tbl = Table([[label_p], [value_p]], colWidths=[width], rowHeights=[12, 22])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DBDB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _kpi_card(label: str, value: str, styles: dict, width: float) -> Table:
    label_p = Paragraph(
        f"<font color='#7F8C8D' size='7'>{label.upper()}</font>",
        styles["SmallText"],
    )
    value_p = Paragraph(
        f"<font color='#2E86AB' size='18'><b>{value}</b></font>",
        ParagraphStyle("kpi_val", fontName="Helvetica-Bold", fontSize=18,
                       textColor=SECONDARY, alignment=TA_LEFT),
    )
    tbl = Table([[label_p], [value_p]], colWidths=[width], rowHeights=[14, 32])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DBDB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _panel(title: str, body, styles: dict, width: float, height: float) -> Table:
    title_p = Paragraph(
        f"<font color='#2C3E50' size='9'><b>{title}</b></font>",
        styles["SmallText"],
    )
    tbl = Table(
        [[title_p], [body]],
        colWidths=[width],
        rowHeights=[18, height],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DBDB")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#D5DBDB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _detail_table(detail: pd.DataFrame) -> Table:
    headers = [
        "Ticker", "Year", "DPS", "Gross_Income_TRY",
        "Net_Income_TRY", "Yield", "Payout_Ratio",
    ]
    rows: list[list[str]] = [headers]
    if detail is None or detail.empty:
        rows.append(["—"] * len(headers))
    else:
        for _, r in detail.sort_values(["Ticker", "Year"]).iterrows():
            rows.append([
                str(r["Ticker"]),
                str(int(r["Year"])),
                _fmt_dps(r["DPS"]),
                format_turkish_number(r["Gross_Income_TRY"]),
                format_turkish_number(r["Net_Income_TRY"]),
                _fmt_pct(r["Yield"]),
                _fmt_pct(r["Payout_Ratio"]),
            ])

    col_widths = [45, 40, 45, 110, 110, 55, 65]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B7BD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DBDB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def build_dividend_dashboard_pdf(
    data: DividendDashboardData,
    tickers_slicer: Iterable[str] | None = None,
    years_slicer: Iterable[int] | None = None,
    report_date: str | None = None,
) -> bytes:
    """Render the Temettü & Sermaye dashboard to a single landscape A4 PDF."""

    if tickers_slicer:
        data = data.filter(tickers=list(tickers_slicer))
    if years_slicer:
        data = data.filter(years=list(years_slicer))

    report_date = report_date or datetime.now().strftime("%d.%m.%Y")

    buf = io.BytesIO()
    page_size = landscape(A4)
    page_width, page_height = page_size
    margin = 28
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title="Temettü & Sermaye Dashboard",
    )

    styles = get_styles()
    available_width = page_width - 2 * margin
    elements: list = []

    # ------------------------------------------------------------------
    # Header bar
    # ------------------------------------------------------------------
    title_p = Paragraph(
        "<font color='white' size='14'><b>Temettü &amp; Sermaye</b></font>",
        ParagraphStyle("dash_title", fontName="Helvetica-Bold", fontSize=14,
                       textColor=WHITE, alignment=TA_LEFT),
    )
    date_p = Paragraph(
        f"<font color='#D4E6F1' size='9'>{report_date}</font>",
        ParagraphStyle("dash_date", fontName="Helvetica", fontSize=9,
                       textColor=WHITE, alignment=TA_RIGHT),
    )
    header = Table(
        [[title_p, date_p]],
        colWidths=[available_width * 0.7, available_width * 0.3],
        rowHeights=[32],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # Slicer row (Ticker + Year)
    # ------------------------------------------------------------------
    ticker_sel = (
        "Select all"
        if not tickers_slicer
        else ", ".join(sorted(set(tickers_slicer)))
    )
    year_sel = (
        "Select all"
        if not years_slicer
        else ", ".join(str(y) for y in sorted(set(years_slicer)))
    )
    slicer_row = Table(
        [[
            _slicer_box("Ticker", ticker_sel, styles, available_width / 2 - 5),
            _slicer_box("Yıl", year_sel, styles, available_width / 2 - 5),
        ]],
        colWidths=[available_width / 2, available_width / 2],
    )
    slicer_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(slicer_row)
    elements.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # KPI cards
    # ------------------------------------------------------------------
    kpis = data.kpis or {}
    card_w = available_width / 4 - 4
    kpi_row = Table(
        [[
            _kpi_card("Brüt Temettü (TRY)", _fmt_money_try(kpis.get("gross_try", 0.0)), styles, card_w),
            _kpi_card("Net Temettü (TRY)", _fmt_money_try(kpis.get("net_try", 0.0)), styles, card_w),
            _kpi_card("Avg Yield", _fmt_pct(kpis.get("avg_yield", 0.0)), styles, card_w),
            _kpi_card("Avg Payout", _fmt_pct(kpis.get("avg_payout", 0.0)), styles, card_w),
        ]],
        colWidths=[available_width / 4] * 4,
    )
    kpi_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(kpi_row)
    elements.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # Chart row (stacked bar + yield/payout trend)
    # ------------------------------------------------------------------
    bar_png = dividend_income_by_ticker_chart(data.by_ticker)
    trend_png = yield_payout_trend_chart(data.by_year)

    left_chart_w = available_width * 0.58 - 6
    right_chart_w = available_width * 0.42 - 6
    chart_height = 210

    bar_img = _img_flowable(bar_png, left_chart_w - 18, chart_height - 28) or Paragraph("", styles["SmallText"])
    trend_img = _img_flowable(trend_png, right_chart_w - 18, chart_height - 28) or Paragraph("", styles["SmallText"])

    chart_row = Table(
        [[
            _panel("Temettü geliri — ticker bazında (brüt + net stacked)",
                   bar_img, styles, left_chart_w, chart_height - 28),
            _panel("Yield & Payout — yıllık trend",
                   trend_img, styles, right_chart_w, chart_height - 28),
        ]],
        colWidths=[available_width * 0.58, available_width * 0.42],
    )
    chart_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(chart_row)
    elements.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # Detail table
    # ------------------------------------------------------------------
    detail_tbl = _detail_table(data.detail)
    elements.append(_panel("Temettü detay tablosu", detail_tbl,
                           styles, available_width, 220))
    elements.append(Spacer(1, 6))

    # ------------------------------------------------------------------
    # Sermaye (Capital) reference page
    # ------------------------------------------------------------------
    elements.append(PageBreak())
    elements.append(Paragraph(
        "<font color='#1B3A5C' size='13'><b>Sermaye — Portföy Pozisyonları</b></font>",
        styles["SectionHeader"],
    ))
    elements.append(Spacer(1, 6))

    positions = get_positions_df()
    cost_png = portfolio_cost_basis_chart(positions)
    cost_img = _img_flowable(cost_png, available_width - 40, 260) or Paragraph("", styles["SmallText"])
    elements.append(cost_img)
    elements.append(Spacer(1, 10))

    # Positions table
    pos_headers = ["Ticker", "Shares", "Own %", "Cost (TRY)", "Cost (USD)",
                   "Avg UC TRY", "Avg UC USD", "İlk Alım"]
    pos_rows: list[list[str]] = [pos_headers]
    for _, r in positions.iterrows():
        pos_rows.append([
            r["ticker"],
            format_turkish_number(r["shares"]),
            _fmt_pct(r["own_pct"], 2),
            format_turkish_number(r["cost_basis_try"]),
            format_turkish_number(r["cost_basis_usd"]),
            _fmt_dps(r["weighted_uc_try"]),
            f"{r['weighted_uc_usd']:,.4f}".replace(",", "X").replace(".", ",").replace("X", "."),
            pd.to_datetime(r["first_acq_date"]).strftime("%d.%m.%Y"),
        ])
    pos_tbl = Table(pos_rows, colWidths=[50, 90, 55, 95, 95, 65, 65, 70], repeatRows=1)
    pos_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B7BD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DBDB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(pos_tbl)

    doc.build(elements)
    return buf.getvalue()
