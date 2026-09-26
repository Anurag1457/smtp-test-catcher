#!/usr/bin/env python3
"""
send_real_email.py — send ONE real test email through a real SMTP account,
to confirm your sending code actually works end-to-end.

This is intentionally scoped to a single message per run, sent to a
recipient you specify explicitly — it is not a bulk sender. If you're
looking to notify your own app's users at scale, that's a different,
larger tool (proper unsubscribe handling, bounce handling, rate limiting,
a verified sending domain) — ask separately if you want that built.

Credentials are read from environment variables, never hardcoded:
    SMTP_HOST      e.g. smtp.gmail.com
    SMTP_PORT      e.g. 587
    SMTP_USER      your account's login (usually your email address)
    SMTP_PASS      your password or, for Gmail/most providers, an
                   "app password" (recommended over your real account
                   password — see README for how to generate one)

Usage:
    export SMTP_HOST=smtp.gmail.com
    export SMTP_PORT=587
    export SMTP_USER=you@gmail.com
    export SMTP_PASS=your_app_password

    python send_real_email.py --to you@gmail.com --subject "Test" --body "Hello, this works."

    # or send HTML:
    python send_real_email.py --to you@gmail.com --subject "Test" --html "<h1>Hi</h1>"

The script always prints exactly who it's about to send to and asks for a
final confirmation before sending, so you never fire off a real email by
accident.
"""

import argparse
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def build_message(sender: str, to: str, subject: str, body: str, html: str | None) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))
    return msg


def main():
    parser = argparse.ArgumentParser(description="Send a single real test email via SMTP.")
    parser.add_argument("--to", required=True, help="Recipient address (send this to yourself for testing)")
    parser.add_argument("--subject", default="Test email", help="Subject line")
    parser.add_argument("--body", default="This is a test email sent from send_real_email.py.", help="Plain-text body")
    parser.add_argument("--html", default=None, help="Optional HTML body")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt (still sends only one message)")
    args = parser.parse_args()

    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")

    missing = [name for name, val in
               [("SMTP_HOST", host), ("SMTP_PORT", port), ("SMTP_USER", user), ("SMTP_PASS", password)]
               if not val]
    if missing:
        print(f"Missing required environment variable(s): {', '.join(missing)}")
        print("Set them first, e.g.:")
        print("  export SMTP_HOST=smtp.gmail.com")
        print("  export SMTP_PORT=587")
        print("  export SMTP_USER=you@example.com")
        print("  export SMTP_PASS=your_app_password")
        sys.exit(1)

    port = int(port)
    msg = build_message(user, args.to, args.subject, args.body, args.html)

    print("About to send ONE real email:")
    print(f"  From:    {user}")
    print(f"  To:      {args.to}")
    print(f"  Subject: {args.subject}")
    print(f"  Via:     {host}:{port}")

    if not args.yes:
        confirm = input("Send this now? [y/N] ").strip().lower()
        if confirm != "y":
            print("Cancelled — nothing was sent.")
            sys.exit(0)

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)
        print(f"Sent to {args.to}.")
    except smtplib.SMTPAuthenticationError:
        print("Authentication failed — check SMTP_USER/SMTP_PASS.")
        print("For Gmail specifically, you likely need an App Password rather than your normal password.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to send: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
