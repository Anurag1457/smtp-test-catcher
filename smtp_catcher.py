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

Rotation (so captured_emails/ doesn't grow forever during a long test run):
    python smtp_catcher.py --max-messages 200      # keep only the 200 newest, delete older
    python smtp_catcher.py --max-age-hours 24      # delete anything older than 24h
    python smtp_catcher.py --max-messages 200 --max-age-hours 24   # both at once
Both are off by default (nothing is deleted unless you set one of these).

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
import time
from datetime import datetime
from email import message_from_bytes

from aiosmtpd.controller import Controller

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_emails")


class CatcherHandler:
    """Accepts every message unconditionally and writes it to disk. Never
    forwards or relays anything — there is no outbound send call anywhere
    in this handler."""

    def __init__(self, capture_dir: str, max_messages: int = 0, max_age_hours: float = 0):
        self.capture_dir = capture_dir
        self.max_messages = max_messages    # 0 = unlimited
        self.max_age_hours = max_age_hours  # 0 = disabled
        os.makedirs(self.capture_dir, exist_ok=True)

    def _eml_files(self):
        """.eml files in capture_dir, oldest first (filenames are timestamps, so
        a plain sort is chronological)."""
        return sorted(f for f in os.listdir(self.capture_dir) if f.endswith(".eml"))

    def rotate(self):
        """Delete captured messages that are past the configured age and/or
        count limits. Called after every new message and on a periodic timer,
        so a long-idle server still cleans up old files."""
        removed = 0

        if self.max_age_hours > 0:
            cutoff = time.time() - (self.max_age_hours * 3600)
            for f in self._eml_files():
                path = os.path.join(self.capture_dir, f)
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                        removed += 1
                except FileNotFoundError:
                    pass

        if self.max_messages > 0:
            files = self._eml_files()
            excess = len(files) - self.max_messages
            for f in files[:max(excess, 0)]:
                path = os.path.join(self.capture_dir, f)
                try:
                    os.remove(path)
                    removed += 1
                except FileNotFoundError:
                    pass

        if removed:
            print(f"[rotate] removed {removed} old captured message(s)")

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

        self.rotate()

        return "250 Message accepted for testing (not delivered anywhere)"


async def periodic_rotation(handler: CatcherHandler, interval_seconds: int = 300):
    """Runs rotation on a timer so old messages still get cleaned up even if
    no new mail arrives to trigger it (relevant mainly for --max-age-hours)."""
    while True:
        await asyncio.sleep(interval_seconds)
        handler.rotate()


def main():
    parser = argparse.ArgumentParser(description="Local SMTP test catcher (no real delivery).")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to listen on (default: 127.0.0.1, localhost only)")
    parser.add_argument("--port", type=int, default=1025, help="Port to listen on (default: 1025)")
    parser.add_argument("--dir", default=CAPTURE_DIR, help="Directory to save captured .eml files")
    parser.add_argument("--max-messages", type=int, default=0,
                         help="Keep only the N newest captured messages, deleting older ones (0 = unlimited, default)")
    parser.add_argument("--max-age-hours", type=float, default=0,
                         help="Delete captured messages older than this many hours (0 = disabled, default)")
    parser.add_argument("--rotate-check-interval", type=int, default=300,
                         help="Seconds between periodic rotation sweeps when idle (default: 300)")
    args = parser.parse_args()

    handler = CatcherHandler(args.dir, max_messages=args.max_messages, max_age_hours=args.max_age_hours)
    handler.rotate()  # clean up anything already past the limits from a previous run
    controller = Controller(handler, hostname=args.host, port=args.port)

    print("=" * 60)
    print("  Local SMTP test catcher")
    print("=" * 60)
    print(f"  Listening on:   {args.host}:{args.port}")
    print(f"  Saving mail to: {args.dir}")
    if args.max_messages > 0:
        print(f"  Rotation:       keep newest {args.max_messages} messages")
    if args.max_age_hours > 0:
        print(f"  Rotation:       delete messages older than {args.max_age_hours}h")
    if not args.max_messages and not args.max_age_hours:
        print("  Rotation:       off (use --max-messages / --max-age-hours to enable)")
    print("  This server does NOT send anything to real recipients.")
    print("  Point your app's SMTP settings here to test it safely.")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    controller.start()
    loop = asyncio.get_event_loop()
    if args.max_age_hours > 0:
        loop.create_task(periodic_rotation(handler, args.rotate_check_interval))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        controller.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
