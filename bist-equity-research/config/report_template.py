"""Report layout and section definitions."""

COLORS = {
    "primary": "#1B3A5C",
    "secondary": "#2E86AB",
    "positive": "#27AE60",
    "negative": "#E74C3C",
    "neutral": "#95A5A6",
    "accent": "#F39C12",
    "background": "#FFFFFF",
    "grid": "#ECF0F1",
    "light_bg": "#F8F9FA",
    "table_header": "#1B3A5C",
    "table_alt_row": "#F2F6FA",
}

FONT_FAMILY = "Helvetica"

SECTIONS = [
    "cover",
    "executive_summary",
    "company_overview",
    "financial_analysis",
    "valuation",
    "technical_analysis",
    "peer_comparison",
    "macro_sector",
    "investment_thesis",
    "risk_factors",
    "esg_governance",
    "appendix",
    "disclaimer",
]

CHART_SPECS = {
    "price_vs_benchmark": {"width": 7, "height": 3.5, "dpi": 300},
    "candlestick": {"width": 7, "height": 4.5, "dpi": 300},
    "revenue_margins": {"width": 7, "height": 3.5, "dpi": 300},
    "eps_pe": {"width": 7, "height": 3.5, "dpi": 300},
    "balance_sheet": {"width": 7, "height": 3.5, "dpi": 300},
    "cash_flow_waterfall": {"width": 7, "height": 3.5, "dpi": 300},
    "football_field": {"width": 7, "height": 3, "dpi": 300},
    "technical_indicators": {"width": 7, "height": 5, "dpi": 300},
    "radar": {"width": 5, "height": 5, "dpi": 300},
    "dividend_history": {"width": 7, "height": 3, "dpi": 300},
    "relative_performance": {"width": 7, "height": 3, "dpi": 300},
}

PAGE_MARGIN = 50  # points
PAGE_WIDTH = 595.27  # A4
PAGE_HEIGHT = 841.89  # A4
