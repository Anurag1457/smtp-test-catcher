# SMTP Test Catcher

A local, offline SMTP server for testing email-sending code. It **accepts**
mail on your machine and **never delivers it anywhere** — no connection to
a real mail server or real recipient is ever made. This is the standard
pattern developers use to test "does my app send the right email with the
right content" without spamming real inboxes or needing real credentials.

## What's included

- `smtp_catcher.py` — the fake SMTP server. Listens locally, saves every
  message it receives as a `.eml` file in `captured_emails/`, and prints a
  one-line log to the console.
- `viewer.py` — a small local web UI (`http://127.0.0.1:8025`) to browse
  captured messages, see headers, and preview the HTML/text body.
- `captured_emails/` — created automatically; holds the raw `.eml` files.

## Setup

```bash
pip install -r requirements.txt
```

## Run it

Terminal 1 — start the catcher:

```bash
python smtp_catcher.py
# Listening on 127.0.0.1:1025
```

Terminal 2 — start the viewer (optional, but nice for reading messages):

```bash
python viewer.py
# Viewer running at http://127.0.0.1:8025
```

Open http://127.0.0.1:8025 in your browser.

## Point your code at it

Any app/script that sends email via SMTP can be pointed at this server
for testing — just swap the host/port, and drop auth/TLS since this dev
tool doesn't require them:

```python
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("This is a test email.")
msg["Subject"] = "Test subject"
msg["From"] = "dev@localhost"
msg["To"] = "test-recipient@localhost"

with smtplib.SMTP("127.0.0.1", 1025) as server:
    server.send_message(msg)
```

Run that, then refresh the viewer — you'll see the message appear.

## Options

```bash
python smtp_catcher.py --host 127.0.0.1 --port 1025 --dir ./captured_emails
python viewer.py --host 127.0.0.1 --port 8025
```

## Rotation

During a long test run, `captured_emails/` can grow without bound if you
don't clean it up. Two optional flags handle that automatically — both are
off by default, so nothing is deleted unless you opt in:

```bash
# keep only the 200 newest messages, deleting older ones as new ones arrive
python smtp_catcher.py --max-messages 200

# delete anything older than 24 hours
python smtp_catcher.py --max-age-hours 24

# both together, checked on every new message and also swept every
# 5 minutes (--rotate-check-interval) in case the server sits idle
python smtp_catcher.py --max-messages 200 --max-age-hours 24
```

Rotation also runs once at startup, so stale files from a previous run get
cleaned up as soon as the limits are set.

## Scope, on purpose

This tool is for local development/testing only:

- It only accepts connections and writes files — there is no code path
  in it that opens an outbound connection to another mail server.
- Binding to `127.0.0.1` (the default) keeps it reachable only from your
  own machine. Don't bind it to `0.0.0.0` or expose it to the internet —
  it has no authentication and isn't hardened for that.
- It's not a substitute for a real transactional/marketing email
  provider (SendGrid, Postmark, SES with a verified domain, etc.) once
  you're ready to actually send mail to real users who've opted in — it
  only exists to let you test the sending code beforehand.
