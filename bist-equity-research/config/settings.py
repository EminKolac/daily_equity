import os
from dotenv import load_dotenv

load_dotenv()

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 4096

# TCMB EVDS
TCMB_EVDS_API_KEY = os.getenv("TCMB_EVDS_API_KEY", "")

# Apify (Twitter/X scraping)
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# Email
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT", "mehmetemin.kolac@tvf.com.tr")

# MCP Endpoints
MCP_SERVERS = {
    "evofin": "https://evo.fintables.com/mcp",
    "quartr": "https://mcp.quartr.com/mcp",
}

# Cache
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
CACHE_TTL_HOURS = 12

# Report
REPORT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
CHART_DPI = 300
