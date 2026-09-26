#!/usr/bin/env python3
"""
smtp_catcher.py — a local, offline SMTP test server for development.

What this does:
  - Listens on localhost for SMTP connections (default: 127.0.0.1:1025)
  - Accepts any message your app / script sends to it
  - Does NOT deliver anything anywhere — no outbound connection is ever
    made to a real mail server or a real recipient
  - Saves every received message to disk as a .eml file (viewable with
    viewer.py, or any email client / text editor)
  - Prints a one-line summary of each message to the console

Use this to test "does my code call the SMTP API correctly and send the
right content" without touching real inboxes, real domains, or a real
mail provider.

Usage:
    python smtp_catcher.py                 # listen on 127.0.0.1:1025
    python smtp_catcher.py --port 2525     # custom port
    python smtp_catcher.py --host 0.0.0.0  # listen on all interfaces (LAN testing only)

Then point whatever you're testing at:
    SMTP host: 127.0.0.1
    SMTP port: 1025
    No auth / no TLS needed (this is a dev tool, not a production server)

Example with Python's smtplib, just to confirm it works:
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText("hello from a test")
    msg["Subject"] = "test message"
    msg["From"] = "dev@localhost"
    msg["To"] = "someone@localhost"
    with smtplib.SMTP("127.0.0.1", 1025) as s:
        s.send_message(msg)
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from email import message_from_bytes

from aiosmtpd.controller import Controller

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_emails")


class CatcherHandler:
    """Accepts every message unconditionally and writes it to disk. Never
    forwards or relays anything — there is no outbound send call anywhere
    in this handler."""

    def __init__(self, capture_dir: str):
        self.capture_dir = capture_dir
        os.makedirs(self.capture_dir, exist_ok=True)

    async def handle_DATA(self, server, session, envelope):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.join(self.capture_dir, f"{timestamp}.eml")

        with open(filename, "wb") as f:
            f.write(envelope.content)

        parsed = message_from_bytes(envelope.content)
        subject = parsed.get("Subject", "(no subject)")
        mail_from = envelope.mail_from
        rcpt_tos = ", ".join(envelope.rcpt_tos)

        print(f"[caught] {timestamp}  from={mail_from}  to={rcpt_tos}  subject={subject!r}")
        print(f"         saved -> {filename}")

        return "250 Message accepted for testing (not delivered anywhere)"


def main():
    parser = argparse.ArgumentParser(description="Local SMTP test catcher (no real delivery).")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to listen on (default: 127.0.0.1, localhost only)")
    parser.add_argument("--port", type=int, default=1025, help="Port to listen on (default: 1025)")
    parser.add_argument("--dir", default=CAPTURE_DIR, help="Directory to save captured .eml files")
    args = parser.parse_args()

    handler = CatcherHandler(args.dir)
    controller = Controller(handler, hostname=args.host, port=args.port)

    print("=" * 60)
    print("  Local SMTP test catcher")
    print("=" * 60)
    print(f"  Listening on:   {args.host}:{args.port}")
    print(f"  Saving mail to: {args.dir}")
    print("  This server does NOT send anything to real recipients.")
    print("  Point your app's SMTP settings here to test it safely.")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    controller.start()
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        controller.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
