"""PDF Report Builder — assembles the full equity research report using ReportLab."""

import io
import logging
import re
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle

from report.styles import (
    get_styles, PRIMARY, SECONDARY, POSITIVE, NEGATIVE, NEUTRAL,
    ACCENT, LIGHT_BG, TABLE_HEADER, TABLE_ALT, DARK_TEXT, WHITE,
    PAGE_WIDTH, PAGE_HEIGHT, MARGIN,
)
from config.tickers import TICKERS

logger = logging.getLogger(__name__)

# Maximum characters per paragraph to avoid ReportLab layout overflow
_MAX_PARAGRAPH_LEN = 5000

# Allowed HTML tags that ReportLab Paragraph supports
_ALLOWED_TAGS_RE = re.compile(
    r"<(/?)("
    r"b|i|u|br|font|sub|sup|strike|strong|em|a|para|span"
    r")(\s[^>]*)?>",
    re.IGNORECASE,
)

# Major sections that warrant a page break before them
_MAJOR_SECTIONS = frozenset({
    "Financial Analysis",
    "Technical Analysis",
    "Investment Thesis",
    "Valuation",
})


def _safe_text(text: Any, max_length: int = _MAX_PARAGRAPH_LEN) -> str:
    """Sanitise arbitrary text for use inside a ReportLab ``Paragraph``.

    - Handles ``None`` and non-string values.
    - Escapes ``&``, ``<``, ``>`` that would break XML parsing while
      preserving already-escaped entities and valid HTML tags (``<b>``,
      ``<i>``, etc.).
    - Truncates to *max_length* characters (adding an ellipsis marker).
    """
    if text is None:
        return ""
    text = str(text)
    if not text:
        return ""

    # --- Step 1: protect existing valid HTML tags by replacing with placeholders ---
    placeholders: list[tuple[str, str]] = []

    def _stash_tag(m: re.Match) -> str:
        token = f"\x00TAG{len(placeholders)}\x00"
        placeholders.append((token, m.group(0)))
        return token

    text = _ALLOWED_TAGS_RE.sub(_stash_tag, text)

    # --- Step 2: escape XML-special characters ---
    # Escape & but not already-escaped entities like &amp; &lt; &#123; etc.
    text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # --- Step 3: restore valid HTML tags ---
    for token, original in placeholders:
        text = text.replace(token, original)

    # --- Step 4: truncate ---
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def _img_from_bytes(png_bytes: bytes, width: float = 480, max_height: float = 300) -> Image | None:
    """Convert PNG bytes to a ReportLab Image flowable.

    Returns ``None`` if the bytes are empty or cannot be decoded so that
    callers can safely skip the image.
    """
    if not png_bytes:
        return None
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO(png_bytes)
    try:
        reader = ImageReader(buf)
        iw, ih = reader.getSize()
        aspect = ih / iw if iw else 1
        actual_height = width * aspect
        if actual_height > max_height:
            actual_height = max_height
            width = max_height / aspect
        buf.seek(0)
        img = Image(buf, width=width, height=actual_height)
        img.hAlign = "CENTER"
        return img
    except Exception:
        logger.warning("Failed to decode image bytes (%d bytes)", len(png_bytes))
        return None


def _recommendation_color(rec: str) -> colors.Color:
    rec_lower = rec.lower()
    if "outperform" in rec_lower or "buy" in rec_lower:
        return POSITIVE
    elif "underperform" in rec_lower or "sell" in rec_lower:
        return NEGATIVE
    return ACCENT


def _build_cover_page(
    elements: list,
    state: dict,
    styles: dict,
    charts: dict,
):
    """Build the cover page."""
    ticker = state["ticker"]
    ticker_meta = TICKERS.get(ticker, {})
    thesis = state.get("investment_thesis", {})
    fundamental = state.get("fundamental_analysis", {})
    valuation = fundamental.get("valuation", {})

    # Cover header block — dark navy background with white text
    elements.append(Spacer(1, 10))

    available_width = PAGE_WIDTH - 2 * MARGIN

    title_para = Paragraph(
        f"{ticker_meta.get('name', ticker)}",
        styles["ReportTitle"]
    )
    subtitle_para = Paragraph(
        f"BIST: {ticker} | {ticker_meta.get('sector', '')} | {state.get('report_date', '')}",
        styles["ReportSubtitle"]
    )

    header_table = Table(
        [[title_para], [subtitle_para]],
        colWidths=[available_width],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (0, 0), 20),
        ("BOTTOMPADDING", (-1, -1), (-1, -1), 18),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15))

    # Recommendation box
    rec = thesis.get("recommendation", "MARKET PERFORM")
    rec_color = _recommendation_color(rec)

    rec_table = Table(
        [[Paragraph(rec, ParagraphStyle(
            "RecBox", fontName="Helvetica-Bold", fontSize=18,
            textColor=WHITE, alignment=TA_CENTER,
        ))]],
        colWidths=[200],
        rowHeights=[40],
    )
    rec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rec_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
    ]))
    elements.append(rec_table)
    elements.append(Spacer(1, 15))

    # Key metrics table
    current_price = valuation.get("current_price", 0)
    market_cap = valuation.get("market_cap", 0)
    pe = valuation.get("pe", 0)
    ff = valuation.get("football_field", {})
    target = ff.get("composite", {}).get("base", 0)
    upside = ff.get("upside_to_base", 0)

    metrics_data = [
        ["Price (TRY)", "Market Cap", "P/E", "Target", "Upside"],
        [
            f"{current_price:,.2f}",
            f"{market_cap/1e9:,.1f} Mrd" if market_cap else "N/A",
            f"{pe:.1f}x" if pe else "N/A",
            f"{target:,.2f}" if target else "N/A",
            f"{upside:+.1f}%" if upside else "N/A",
        ],
    ]
    metrics_table = Table(metrics_data, colWidths=[95] * 5)
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 11),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK_TEXT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 15))

    # Score summary bar
    comp_scores = state.get("investment_thesis", {}).get("composite_score", {})
    if comp_scores:
        score_labels = ["Fundamental", "Technical", "Macro", "Sentiment"]
        score_keys = ["fundamental", "technical", "macro", "sentiment"]
        score_header = [Paragraph(f"<b>{lbl}</b>", ParagraphStyle(
            f"ScoreH_{lbl}", fontName="Helvetica-Bold", fontSize=7,
            textColor=WHITE, alignment=TA_CENTER,
        )) for lbl in score_labels]
        score_values = []
        for key in score_keys:
            val = comp_scores.get(key, 0)
            # Color-code: green >=60, amber 40-60, red <40
            if val >= 60:
                sc = POSITIVE
            elif val >= 40:
                sc = ACCENT
            else:
                sc = NEGATIVE
            score_values.append(Paragraph(
                f"<b>{val:.0f}/100</b>",
                ParagraphStyle(f"ScoreV_{key}", fontName="Helvetica-Bold",
                               fontSize=11, textColor=sc, alignment=TA_CENTER),
            ))
        score_bar = Table(
            [score_header, score_values],
            colWidths=[available_width / 4] * 4,
        )
        score_bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BG),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
        ]))
        elements.append(score_bar)
        elements.append(Spacer(1, 10))

    # 1-line thesis
    final_thesis = thesis.get("final_thesis", "")
    if final_thesis:
        elements.append(Paragraph(
            f"<b>Investment Thesis:</b> {_safe_text(final_thesis, 300)}",
            styles["BodyText2"]
        ))
    elements.append(Spacer(1, 10))

    # Price vs benchmark chart
    if "price_vs_benchmark" in charts:
        try:
            img = _img_from_bytes(charts["price_vs_benchmark"], width=460, max_height=220)
            if img:
                elements.append(img)
        except Exception:
            logger.warning("Failed to embed price_vs_benchmark chart on cover page")

    elements.append(PageBreak())


def _build_section(
    elements: list,
    title: str,
    content: str,
    styles: dict,
    chart_bytes: bytes | None = None,
    chart_width: float = 460,
    chart_height: float = 250,
    extra_table: Table | None = None,
    page_break_before: bool = False,
):
    """Build a generic report section.

    If *page_break_before* is ``True`` a ``PageBreak`` is inserted before
    the section header.  This replaces the old pattern of manually adding
    ``PageBreak`` after every section.
    """
    if page_break_before:
        elements.append(PageBreak())

    elements.append(Paragraph(_safe_text(title), styles["SectionHeader"]))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=SECONDARY, spaceAfter=6,
    ))

    if content:
        # Split paragraphs on double-newlines first, then single newlines
        paragraphs = content.split("\n\n") if "\n\n" in content else content.split("\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            safe = _safe_text(para)
            try:
                elements.append(Paragraph(safe, styles["BodyText2"]))
            except Exception:
                # If the paragraph still fails (e.g. deeply broken markup),
                # fall back to a plain-text version with all tags stripped.
                fallback = re.sub(r"<[^>]+>", "", safe)
                logger.warning("Paragraph XML parse failed; using stripped fallback")
                elements.append(Paragraph(fallback, styles["BodyText2"]))

    if chart_bytes:
        try:
            img = _img_from_bytes(chart_bytes, width=chart_width, max_height=chart_height)
            if img:
                elements.append(Spacer(1, 8))
                elements.append(img)
        except Exception:
            logger.warning("Failed to embed chart in section '%s'", title)

    if extra_table:
        elements.append(Spacer(1, 8))
        elements.append(extra_table)

    elements.append(Spacer(1, 10))


def _build_indicators_table(technical: dict, styles: dict) -> Table:
    """Build technical indicators summary table."""
    indicators = technical.get("indicators", {})
    trend = indicators.get("trend", {})
    momentum = indicators.get("momentum", {})

    data = [
        ["Indicator", "Value", "Signal"],
        ["SMA(20)", f"{trend.get('sma_20', 'N/A')}", trend.get("price_vs_sma200", "")],
        ["SMA(50)", f"{trend.get('sma_50', 'N/A')}", ""],
        ["SMA(200)", f"{trend.get('sma_200', 'N/A')}", "Golden Cross" if trend.get("golden_cross") else ""],
        ["RSI(14)", f"{momentum.get('rsi_14', 'N/A')}", ""],
        ["MACD", f"{momentum.get('macd', 'N/A')}", ""],
        ["ADX", f"{trend.get('adx', 'N/A')}", ""],
    ]

    table = Table(data, colWidths=[150, 150, 150])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TABLE_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _build_consensus_table(sentiment: dict, styles: dict) -> Table:
    """Build analyst consensus table."""
    consensus = sentiment.get("analyst_consensus", {})
    data = [
        ["Buy", "Hold", "Sell", "Avg Target", "Upside"],
        [
            str(consensus.get("buy", 0)),
            str(consensus.get("hold", 0)),
            str(consensus.get("sell", 0)),
            f"{consensus.get('avg_target', 0):,.2f}",
            f"{consensus.get('target_vs_current', 0):+.1f}%",
        ],
    ]

    table = Table(data, colWidths=[80, 80, 80, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_pdf(state: dict) -> bytes:
    """Build the full PDF report from pipeline state.

    Returns PDF as bytes.
    """
    ticker = state["ticker"]
    logger.info("Building PDF for %s", ticker)

    styles = get_styles()
    charts = state.get("charts", {})
    sections = state.get("report_sections", {})
    fundamental = state.get("fundamental_analysis", {})
    technical = state.get("technical_analysis", {})
    macro = state.get("macro_analysis", {})
    sentiment = state.get("sentiment_analysis", {})
    thesis = state.get("investment_thesis", {})

    buf = io.BytesIO()

    def header_footer(canvas, doc):
        """Draw header and footer on each page."""
        canvas.saveState()
        # Header line
        canvas.setStrokeColor(SECONDARY)
        canvas.setLineWidth(1)
        canvas.line(MARGIN, PAGE_HEIGHT - 35, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 35)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(NEUTRAL)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 30,
                         f"{TICKERS.get(ticker, {}).get('name', ticker)} | BIST: {ticker}")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 30,
                               f"Equity Research Report | {state.get('report_date', '')}")

        # Footer
        canvas.line(MARGIN, 35, PAGE_WIDTH - MARGIN, 35)
        canvas.drawCentredString(PAGE_WIDTH / 2, 22, f"Page {doc.page}")
        canvas.drawString(MARGIN, 22, "BIST Equity Research")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 22, "Confidential")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 10,
        bottomMargin=MARGIN,
        title=f"{ticker} Equity Research Report",
        author="BIST Equity Research System",
    )

    elements = []

    # Page 1: Cover
    _build_cover_page(elements, state, styles, charts)

    # -- Helper to safely embed a chart from the charts dict -----------------
    def _embed_chart(key: str, width: float = 460, max_height: float = 230):
        """Append chart image if present and valid; silently skip otherwise."""
        raw = charts.get(key)
        if not raw:
            return
        try:
            img = _img_from_bytes(raw, width=width, max_height=max_height)
            if img:
                elements.append(Spacer(1, 8))
                elements.append(img)
        except Exception:
            logger.warning("Failed to embed chart '%s'", key)

    # Page 2: Executive Summary
    _build_section(
        elements, "Executive Summary",
        sections.get("EXECUTIVE_SUMMARY", thesis.get("final_thesis", "")),
        styles,
        chart_bytes=charts.get("radar"),
        chart_width=300,
        chart_height=300,
    )

    # Composite Scores Table
    comp_scores = thesis.get("composite_score", {})
    if comp_scores:
        elements.append(Spacer(1, 6))
        scores_data = [["Factor", "Score", "Weight"]]
        factor_weights = {"fundamental": "30%", "technical": "25%", "macro": "20%", "sentiment": "25%"}
        for factor in ["fundamental", "technical", "macro", "sentiment"]:
            val = comp_scores.get(factor, 50)
            scores_data.append([factor.capitalize(), f"{val:.0f}/100", factor_weights.get(factor, "")])
        scores_data.append(["Overall", f"{comp_scores.get('overall', 50):.0f}/100", "100%"])

        scores_table = Table(scores_data, colWidths=[150, 100, 80])
        scores_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TABLE_ALT]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8F6F3")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(scores_table)

    # Conviction level
    conviction = thesis.get("conviction", "Medium")
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"<b>Conviction Level:</b> {_safe_text(conviction)} | "
        f"<b>Risk/Reward:</b> {_safe_text(str(thesis.get('risk_reward_ratio', 'N/A')))}x",
        styles["BodyText2"]
    ))

    # Company Overview — minor section, no page break
    _build_section(
        elements, "Company Overview",
        sections.get("COMPANY_OVERVIEW", ""),
        styles,
    )

    # Financial Analysis — MAJOR section, page break before
    _build_section(
        elements, "Financial Analysis",
        sections.get("FINANCIAL_ANALYSIS", ""),
        styles,
        chart_bytes=charts.get("revenue_margins"),
        page_break_before=True,
    )

    # Financial Health Scoring Table
    health = fundamental.get("financial_health", {})
    piotroski = health.get("piotroski_f", {})
    altman = health.get("altman_z", {})
    eq = health.get("earnings_quality", {})
    dupont = fundamental.get("dupont", {})

    if piotroski or altman or dupont:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Financial Health Scorecard", styles["SubSectionHeader"]))
        health_data = [
            ["Metric", "Value", "Assessment"],
        ]
        if piotroski:
            health_data.append([
                "Piotroski F-Score", f"{piotroski.get('score', 'N/A')}/9",
                _safe_text(piotroski.get("interpretation", "N/A")),
            ])
        if altman:
            health_data.append([
                "Altman Z-Score", f"{altman.get('z_score', 'N/A')}",
                _safe_text(altman.get("zone", "N/A")),
            ])
        if eq:
            health_data.append([
                "Earnings Quality", f"CF/NI: {eq.get('cf_vs_net_income', 'N/A')}",
                _safe_text(eq.get("quality", "N/A")),
            ])
        if dupont:
            health_data.append([
                "DuPont ROE",
                f"{dupont.get('roe', 0):.1f}%",
                _safe_text(str(dupont.get("decomposition", "N/A"))),
            ])

        health_table = Table(health_data, colWidths=[120, 100, 230])
        health_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TABLE_ALT]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(health_table)

    _embed_chart("balance_sheet")
    _embed_chart("cash_flow_waterfall")
    _embed_chart("eps_pe")

    # Valuation — MAJOR section, page break before
    _build_section(
        elements, "Valuation",
        sections.get("VALUATION_DISCUSSION", ""),
        styles,
        chart_bytes=charts.get("football_field"),
        page_break_before=True,
    )

    # DCF assumptions table
    dcf = fundamental.get("valuation", {}).get("dcf", {})
    if dcf.get("assumptions"):
        assumptions = dcf["assumptions"]
        dcf_data = [
            ["Assumption", "Value"],
            ["WACC", f"{assumptions.get('wacc', 0)*100:.1f}%"],
            ["Growth Rate (5Y)", f"{assumptions.get('growth_rate_5y', 0)*100:.1f}%"],
            ["Terminal Growth", f"{assumptions.get('terminal_growth', 0)*100:.1f}%"],
            ["DCF Fair Value", f"{dcf.get('fair_value', 0):,.2f} TRY"],
            ["PV of FCFs", f"{dcf.get('pv_fcfs', 0):,.2f} TRY"],
            ["PV of Terminal Value", f"{dcf.get('pv_terminal', 0):,.2f} TRY"],
        ]
        dcf_table = Table(dcf_data, colWidths=[220, 220])
        dcf_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TABLE_ALT]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(dcf_table)

    # DCF Sensitivity Table (WACC vs Terminal Growth)
    sensitivity = fundamental.get("valuation", {}).get("sensitivity", {})
    if sensitivity:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("DCF Sensitivity (WACC vs Terminal Growth)", styles["SubSectionHeader"]))
        try:
            import pandas as pd
            if isinstance(sensitivity, dict):
                sens_df = pd.DataFrame(sensitivity)
                if not sens_df.empty:
                    headers = [""] + list(sens_df.columns)
                    sens_table_data = [headers]
                    for idx, row in sens_df.iterrows():
                        sens_table_data.append([str(idx)] + [f"{v:,.2f}" for v in row.values])

                    n_cols = len(headers)
                    col_width = min(80, int(450 / n_cols))
                    sens_table = Table(sens_table_data, colWidths=[col_width] * n_cols)
                    sens_table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), SECONDARY),
                        ("BACKGROUND", (0, 0), (0, -1), SECONDARY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                        ("TEXTCOLOR", (0, 0), (0, -1), WHITE),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
                        ("ROWBACKGROUNDS", (1, 1), (-1, -1), [WHITE, TABLE_ALT]),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]))
                    elements.append(sens_table)
        except Exception as e:
            logger.error("Sensitivity table build failed: %s", e)

    # Technical Analysis — MAJOR section, page break before
    _build_section(
        elements, "Technical Analysis",
        sections.get("TECHNICAL_ANALYSIS_TEXT", technical.get("technical_summary", "")),
        styles,
        chart_bytes=charts.get("technical_indicators"),
        chart_height=320,
        page_break_before=True,
    )
    elements.append(_build_indicators_table(technical, styles))

    # Support/Resistance
    key_levels = technical.get("key_levels", {})
    if key_levels:
        support = key_levels.get("support", [])
        resistance = key_levels.get("resistance", [])
        levels_data = [["Support Levels", "Resistance Levels"]]
        max_len = max(len(support), len(resistance), 1)
        for i in range(min(max_len, 4)):
            s = f"{support[i]:,.2f}" if i < len(support) else ""
            r = f"{resistance[i]:,.2f}" if i < len(resistance) else ""
            levels_data.append([s, r])
        levels_table = Table(levels_data, colWidths=[220, 220])
        levels_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(levels_table)

    _embed_chart("candlestick", max_height=280)

    # Peer Comparison — minor section, no forced page break
    _build_section(
        elements, "Peer Comparison",
        "Relative valuation comparison with sector peers.",
        styles,
        chart_bytes=charts.get("relative_performance"),
    )

    # Macro & Sector — minor section, no forced page break
    _build_section(
        elements, "Macro & Sector Analysis",
        sections.get("MACRO_SECTOR", macro.get("macro_thesis", "")),
        styles,
    )

    # Sentiment & Consensus — minor section
    _build_section(
        elements, "Market Sentiment",
        sentiment.get("sentiment_summary", ""),
        styles,
    )
    elements.append(_build_consensus_table(sentiment, styles))

    # Twitter commentary
    twitter = sentiment.get("twitter_commentary", {})
    if twitter.get("narrative_summary"):
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(
            f"<b>Social Media Commentary (X/Twitter):</b> "
            f"{_safe_text(twitter['narrative_summary'])}",
            styles["BodyText2"]
        ))

    # Investment Thesis — MAJOR section, page break before
    _build_section(
        elements, "Investment Thesis",
        sections.get("INVESTMENT_THESIS", thesis.get("final_thesis", "")),
        styles,
        page_break_before=True,
    )

    # Bull/Bear boxes
    bull = thesis.get("bull_case", {})
    bear = thesis.get("bear_case", {})

    bull_text = f"<b>Bull Case:</b> {_safe_text(bull.get('thesis', 'N/A'), 400)}"
    bear_text = f"<b>Bear Case:</b> {_safe_text(bear.get('thesis', 'N/A'), 400)}"

    elements.append(Paragraph(bull_text, ParagraphStyle(
        "BullText", parent=styles["BodyText2"], textColor=POSITIVE,
    )))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(bear_text, ParagraphStyle(
        "BearText", parent=styles["BodyText2"], textColor=NEGATIVE,
    )))

    # Catalysts
    catalysts = thesis.get("catalysts", [])
    if catalysts:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>Key Catalysts:</b>", styles["SubSectionHeader"]))
        for c in catalysts[:5]:
            elements.append(Paragraph(f"\u2022 {_safe_text(c)}", styles["BodyText2"]))

    # Risk Factors — minor section, no forced page break
    _build_section(
        elements, "Risk Factors",
        sections.get("RISK_FACTORS", ""),
        styles,
    )

    # ESG & Governance — minor section
    _build_section(
        elements, "ESG & Governance",
        sections.get("ESG_GOVERNANCE", ""),
        styles,
    )
    _embed_chart("dividend_history", max_height=200)

    # Disclaimer — always on a fresh page
    elements.append(PageBreak())
    elements.append(Paragraph("Disclaimer", styles["SectionHeader"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=SECONDARY, spaceAfter=8))
    disclaimer_text = (
        "This report is prepared for informational purposes only and does not constitute "
        "investment advice, a recommendation, or an offer to buy or sell any securities. "
        "The information contained herein is based on sources believed to be reliable, but "
        "no representation or warranty, express or implied, is made as to its accuracy, "
        "completeness, or timeliness.\n\n"
        "Past performance is not indicative of future results. Investments in securities "
        "involve risk, including the possible loss of principal. The analysis, opinions, "
        "and estimates expressed in this report are subject to change without notice.\n\n"
        "This report was generated by an automated equity research system using AI-assisted "
        "analysis. All data sourced from Fintables/evofin, Yahoo Finance, Is Yatirim, "
        "TCMB EVDS, KAP, and other publicly available sources. Users should conduct their "
        "own due diligence before making investment decisions.\n\n"
        "BIST (Borsa Istanbul) listed securities are subject to Turkish capital markets "
        "regulations. Foreign investors should consider currency risk (TRY) and "
        "country-specific regulatory risks.\n\n"
        f"\u00a9 {datetime.now().year} BIST Equity Research. All rights reserved."
    )
    elements.append(Paragraph(disclaimer_text, styles["Disclaimer"]))

    # Build PDF
    doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer)
    buf.seek(0)
    pdf_bytes = buf.read()
    logger.info("PDF built for %s: %d bytes, estimated %d pages",
                ticker, len(pdf_bytes), len(elements) // 10)
    return pdf_bytes
