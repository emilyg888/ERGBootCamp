"""
ERGBootCamp — send_whatsapp.py

Sends the daily coaching brief via Twilio WhatsApp Sandbox.
Called by the launchd job at 06:30 every morning, or manually.

Usage:
    python pipelines/send_whatsapp.py             # generate + send
    python pipelines/send_whatsapp.py --brief-only # send latest saved brief
"""

import sys
import os
from pathlib import Path
from datetime import date

from pipelines.config_loader import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO, BRIEFS_DIR,
)


def load_brief() -> str | None:
    """Load today's brief, falling back to latest.txt."""
    today_path = BRIEFS_DIR / f"{date.today().isoformat()}.txt"
    latest_path = BRIEFS_DIR / "latest.txt"

    for p in [today_path, latest_path]:
        if p.exists():
            return p.read_text().strip()
    return None


def send_whatsapp(message: str) -> dict:
    """Send message via Twilio WhatsApp API."""
    from twilio.rest import Client

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        raise ValueError(
            "Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN in config/.env"
        )

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    msg = client.messages.create(
        from_=TWILIO_FROM,
        to=TWILIO_TO,
        body=message,
    )

    return {"sid": msg.sid, "status": msg.status, "to": TWILIO_TO}


def main():
    brief_only = "--brief-only" in sys.argv

    if not brief_only:
        # run the full brief generation pipeline first
        from pipelines.generate_daily_brief import main as gen_brief
        gen_brief()

    brief = load_brief()
    if not brief:
        print("No brief found. Run generate_daily_brief.py first.")
        sys.exit(1)

    print(f"Sending WhatsApp brief to {TWILIO_TO}...")
    result = send_whatsapp(brief)
    print(f"Sent! SID: {result['sid']} | Status: {result['status']}")


if __name__ == "__main__":
    main()
