#!/usr/bin/env python3
"""BIST Equity Research Report Generator — CLI entry point."""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import ANTHROPIC_API_KEY, MODEL, LLM_TEMPERATURE, REPORT_OUTPUT_DIR
from config.tickers import TICKERS, TICKER_LIST
from agents.orchestrator import run_research_pipeline
from report.pdf_builder import build_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_llm():
    """Initialize Anthropic LLM via LangChain."""
    if not ANTHROPIC_API_KEY:
        logger.warning("No ANTHROPIC_API_KEY set — running without LLM narratives")
        return None
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=4096,
            anthropic_api_key=ANTHROPIC_API_KEY,
        )
    except ImportError:
        try:
            from langchain.chat_models import ChatAnthropic
            return ChatAnthropic(
                model=MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=4096,
                anthropic_api_key=ANTHROPIC_API_KEY,
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed — no LLM")
            return None


async def generate_report(ticker: str, output_path: str | None = None) -> str:
    """Generate a full equity research report for a BIST ticker.

    Returns the output file path.
    """
    import time as _time
    t0 = _time.time()
    logger.info("=" * 60)
    logger.info("Generating report for %s", ticker)
    logger.info("=" * 60)

    llm = get_llm()

    # Run the research pipeline
    state = await run_research_pipeline(ticker=ticker, llm=llm)

    # Build PDF
    try:
        pdf_bytes = build_pdf(state)
    except Exception as e:
        logger.error("PDF build failed for %s: %s", ticker, e)
        raise

    # Save
    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
    if output_path is None:
        date_str = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(REPORT_OUTPUT_DIR, f"{ticker}_report_{date_str}.pdf")

    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    elapsed = _time.time() - t0
    logger.info("Report saved: %s (%d bytes, %.1fs)", output_path, len(pdf_bytes), elapsed)
    return output_path


async def generate_all_reports(tickers: list[str] | None = None) -> list[str]:
    """Generate reports for all tickers (or a subset)."""
    if tickers is None:
        tickers = TICKER_LIST

    reports = []
    failed = []
    for ticker in tickers:
        try:
            path = await generate_report(ticker)
            reports.append(path)
            logger.info("SUCCESS: %s", ticker)
        except Exception as e:
            logger.error("FAILED: %s — %s", ticker, e)
            failed.append(ticker)

    logger.info("=" * 60)
    logger.info("BATCH COMPLETE: %d/%d reports generated", len(reports), len(tickers))
    if failed:
        logger.warning("Failed tickers: %s", ", ".join(failed))
    logger.info("=" * 60)
    return reports


def main():
    parser = argparse.ArgumentParser(
        description="BIST Equity Research Report Generator"
    )
    parser.add_argument(
        "--ticker", "-t",
        type=str,
        help="Single ticker to analyze (e.g., THYAO)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Generate reports for all 11 tickers",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        help="List of tickers to analyze",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output PDF path (only for single ticker)",
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send reports via email after generation",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear data cache before running",
    )

    args = parser.parse_args()

    if args.clear_cache:
        import shutil
        from config.settings import CACHE_DIR
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            logger.info("Cache cleared: %s", CACHE_DIR)

    if args.all:
        reports = asyncio.run(generate_all_reports())
        if args.send_email:
            from scheduler import send_reports_email
            send_reports_email(reports)
    elif args.tickers:
        reports = asyncio.run(generate_all_reports(args.tickers))
        if args.send_email:
            from scheduler import send_reports_email
            send_reports_email(reports)
    elif args.ticker:
        if args.ticker not in TICKERS:
            logger.warning("Ticker %s not in coverage universe. Proceeding anyway.", args.ticker)
        report = asyncio.run(generate_report(args.ticker, args.output))
        if args.send_email:
            from scheduler import send_reports_email
            send_reports_email([report])
        print(f"Report generated: {report}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
