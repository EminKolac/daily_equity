"""Consistent chart styling for all report charts."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

COLORS = {
    "primary": "#1B3A5C",
    "secondary": "#2E86AB",
    "positive": "#27AE60",
    "negative": "#E74C3C",
    "neutral": "#95A5A6",
    "accent": "#F39C12",
    "background": "#FFFFFF",
    "grid": "#ECF0F1",
    "light_blue": "#D4E6F1",
    "dark_text": "#2C3E50",
}

FONT_FAMILY = "Helvetica"
DPI = 300


def apply_style(ax, title: str = "", xlabel: str = "", ylabel: str = ""):
    """Apply consistent styling to a matplotlib axes."""
    ax.set_facecolor(COLORS["background"])
    ax.figure.set_facecolor(COLORS["background"])

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])

    ax.tick_params(colors=COLORS["dark_text"], labelsize=8)
    ax.grid(True, alpha=0.3, color=COLORS["grid"], linestyle="--")

    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", color=COLORS["primary"],
                      pad=10, fontfamily=FONT_FAMILY)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color=COLORS["dark_text"], fontfamily=FONT_FAMILY)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=COLORS["dark_text"], fontfamily=FONT_FAMILY)


def create_figure(width: float = 7, height: float = 3.5, nrows: int = 1, ncols: int = 1,
                  **kwargs):
    """Create a styled figure."""
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(width, height),
                              facecolor=COLORS["background"], **kwargs)
    fig.patch.set_facecolor(COLORS["background"])
    return fig, axes


def format_turkish_number(value: float, decimals: int = 0) -> str:
    """Format number with Turkish conventions (dot=thousands, comma=decimal)."""
    if abs(value) >= 1e9:
        return f"{value/1e9:,.{decimals}f} Mrd".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(value) >= 1e6:
        return f"{value/1e6:,.{decimals}f} Mn".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def save_chart(fig, dpi: int = DPI) -> bytes:
    """Save figure to PNG bytes."""
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
