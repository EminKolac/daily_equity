#!/usr/bin/env bash
# BIST Equity Research — Weekly Report Runner
# Runs every Sunday at 10:00 AM Istanbul time via cron
# Cron entry (UTC+3 = 07:00 UTC):
#   0 7 * * 0 /home/user/daily_equity/bist-equity-research/run_weekly.sh >> /var/log/bist-research.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Set timezone
export TZ="Europe/Istanbul"

echo "=============================================="
echo "BIST Equity Research — Weekly Run"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=============================================="

# Run the pipeline for all 11 tickers and send email
python3 "$SCRIPT_DIR/main.py" --all --send-email

echo "=============================================="
echo "Weekly run completed: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=============================================="
