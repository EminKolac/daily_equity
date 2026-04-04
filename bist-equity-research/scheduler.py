#!/usr/bin/env python3
"""Weekly scheduler — runs reports every Sunday at 10:00 AM Istanbul time and emails them."""

import asyncio
import logging
import os
import smtplib
import sys
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, REPORT_RECIPIENT,
)
from config.tickers import TICKER_LIST, TICKERS
from main import generate_all_reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def send_reports_email(report_paths: list[str], recipient: str | None = None):
    """Send generated reports as email attachments."""
    recipient = recipient or REPORT_RECIPIENT
    if not all([SMTP_USER, SMTP_PASSWORD, recipient]):
        logger.error(
            "Email config incomplete. Set SMTP_USER, SMTP_PASSWORD, and REPORT_RECIPIENT."
        )
        return False

    date_str = datetime.now().strftime("%Y-%m-%d")

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = recipient
    msg["Subject"] = f"BIST Equity Research Reports — {date_str}"

    # Body
    ticker_list = ", ".join(TICKER_LIST)
    body = f"""Merhaba,

Haftalık BIST hisse senedi araştırma raporları ekte sunulmuştur.

Kapsam: {ticker_list}
Tarih: {date_str}
Rapor Sayısı: {len(report_paths)}

Bu raporlar otomatik olarak oluşturulmuştur. Yatırım tavsiyesi niteliği taşımamaktadır.

---
Weekly BIST equity research reports are attached.

Coverage: {ticker_list}
Date: {date_str}
Reports: {len(report_paths)}

These reports are auto-generated. Not investment advice.

İyi çalışmalar,
BIST Equity Research System
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Attach PDFs
    for path in report_paths:
        if not os.path.exists(path):
            logger.warning("Report file not found: %s", path)
            continue
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

    # Send with retry
    import time
    for attempt in range(3):
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            logger.info("Email sent to %s with %d attachments", recipient, len(report_paths))
            return True
        except Exception as e:
            logger.error("Email send attempt %d/3 failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    return False


async def weekly_job():
    """Run the full weekly report generation and email pipeline."""
    logger.info("=" * 70)
    logger.info("WEEKLY JOB STARTED: %s", datetime.now().isoformat())
    logger.info("Generating reports for %d tickers: %s", len(TICKER_LIST), ", ".join(TICKER_LIST))
    logger.info("=" * 70)

    reports = await generate_all_reports()
    logger.info("Generated %d reports", len(reports))

    if reports:
        success = send_reports_email(reports)
        if success:
            logger.info("Weekly job complete — reports emailed to %s", REPORT_RECIPIENT)
        else:
            logger.error("Weekly job complete — email delivery FAILED")
    else:
        logger.error("Weekly job complete — NO reports generated")


def run_scheduler():
    """Run the scheduler that triggers every Sunday at 10:00 AM Istanbul time."""
    import schedule
    import time

    # Set timezone for Istanbul
    os.environ["TZ"] = "Europe/Istanbul"
    try:
        time.tzset()
    except AttributeError:
        pass  # Windows doesn't have tzset

    def job_wrapper():
        asyncio.run(weekly_job())

    schedule.every().sunday.at("10:00").do(job_wrapper)

    logger.info("Scheduler started. Next run: Sunday 10:00 AM Istanbul time.")
    logger.info("Coverage: %s", ", ".join(TICKER_LIST))
    logger.info("Recipient: %s", REPORT_RECIPIENT)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        # Run immediately (for testing)
        asyncio.run(weekly_job())
    else:
        run_scheduler()
