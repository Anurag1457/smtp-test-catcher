#!/usr/bin/env python3
"""
viewer.py — a tiny local web UI to browse messages captured by smtp_catcher.py.

Reads .eml files from the captured_emails/ directory and renders them in
your browser. Read-only, no network calls, nothing is sent anywhere.

Usage:
    python viewer.py                # serves at http://127.0.0.1:8025
    python viewer.py --port 9000
"""

import argparse
import html
import os
from datetime import datetime
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_emails")

PAGE_STYLE = """
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; margin: 0; background: #f5f6f8; color: #1a1d23; }
  header { background: #1a1d23; color: #fff; padding: 16px 24px; }
  header h1 { margin: 0; font-size: 18px; font-weight: 600; }
  header p { margin: 4px 0 0; font-size: 13px; color: #9aa0aa; }
  .layout { display: flex; height: calc(100vh - 61px); }
  .list { width: 340px; overflow-y: auto; border-right: 1px solid #e1e4e8; background: #fff; }
  .item { padding: 12px 16px; border-bottom: 1px solid #eef0f2; cursor: pointer; text-decoration: none; color: inherit; display: block; }
  .item:hover { background: #f5f6f8; }
  .item.active { background: #eef2ff; border-left: 3px solid #4f5bd5; }
  .item .subject { font-weight: 600; font-size: 13px; margin-bottom: 2px; }
  .item .meta { font-size: 12px; color: #6b7280; }
  .detail { flex: 1; overflow-y: auto; padding: 24px; }
  .detail-card { background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; padding: 20px; max-width: 800px; }
  .field { margin-bottom: 6px; font-size: 13px; }
  .field b { display: inline-block; width: 70px; color: #6b7280; }
  .body-frame { margin-top: 16px; border: 1px solid #e1e4e8; border-radius: 6px; width: 100%; min-height: 400px; }
  .empty { padding: 40px; color: #6b7280; text-align: center; }
  .badge { display: inline-block; background: #eef2ff; color: #4f5bd5; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: 6px; }
</style>
"""


def list_messages():
    if not os.path.isdir(CAPTURE_DIR):
        return []
    files = [f for f in os.listdir(CAPTURE_DIR) if f.endswith(".eml")]
    files.sort(reverse=True)
    return files


def load_message(filename):
    path = os.path.join(CAPTURE_DIR, filename)
    with open(path, "rb") as f:
        return message_from_bytes(f.read())


def get_body(msg):
    if msg.is_multipart():
        html_part, text_part = None, None
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and html_part is None:
                html_part = part.get_payload(decode=True)
            elif ctype == "text/plain" and text_part is None:
                text_part = part.get_payload(decode=True)
        if html_part:
            return html_part.decode(errors="replace"), "html"
        if text_part:
            return text_part.decode(errors="replace"), "text"
        return "(no readable body)", "text"
    else:
        payload = msg.get_payload(decode=True) or b""
        ctype = msg.get_content_type()
        return payload.decode(errors="replace"), ("html" if ctype == "text/html" else "text")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep console quiet

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/":
            self.render_index(qs.get("msg", [None])[0])
        elif parsed.path == "/raw":
            self.render_raw(qs.get("msg", [None])[0])
        else:
            self.send_response(404)
            self.end_headers()

    def render_raw(self, filename):
        files = list_messages()
        if not filename or filename not in files:
            self.send_response(404)
            self.end_headers()
            return
        msg = load_message(filename)
        body, kind = get_body(msg)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8" if kind == "html" else "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def render_index(self, selected):
        files = list_messages()

        list_html = ""
        if not files:
            list_html = "<div class='empty'>No messages captured yet.<br>Send a test email to this server to see it here.</div>"
        for f in files:
            msg = load_message(f)
            subject = html.escape(msg.get("Subject", "(no subject)"))
            frm = html.escape(msg.get("From", ""))
            ts = f.replace(".eml", "")
            try:
                pretty_ts = datetime.strptime(ts, "%Y%m%d_%H%M%S_%f").strftime("%b %d, %H:%M:%S")
            except ValueError:
                pretty_ts = ts
            active = "active" if f == selected else ""
            list_html += (
                f"<a class='item {active}' href='/?msg={f}'>"
                f"<div class='subject'>{subject}</div>"
                f"<div class='meta'>{frm} &middot; {pretty_ts}</div>"
                f"</a>"
            )

        detail_html = "<div class='empty'>Select a message on the left to preview it.</div>"
        if selected and selected in files:
            msg = load_message(selected)
            subject = html.escape(msg.get("Subject", "(no subject)"))
            frm = html.escape(msg.get("From", ""))
            to = html.escape(msg.get("To", ""))
            date = html.escape(msg.get("Date", ""))
            body, kind = get_body(msg)
            detail_html = f"""
              <div class="detail-card">
                <div class="field"><b>Subject</b>{subject}<span class="badge">not delivered</span></div>
                <div class="field"><b>From</b>{frm}</div>
                <div class="field"><b>To</b>{to}</div>
                <div class="field"><b>Date</b>{date}</div>
                <iframe class="body-frame" src="/raw?msg={selected}" sandbox=""></iframe>
              </div>
            """

        page = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>SMTP Test Catcher</title>
          {PAGE_STYLE}
        </head>
        <body>
          <header>
            <h1>SMTP Test Catcher</h1>
            <p>Local dev tool — messages shown here were never sent to a real recipient.</p>
          </header>
          <div class="layout">
            <div class="list">{list_html}</div>
            <div class="detail">{detail_html}</div>
          </div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Web viewer for captured test emails.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8025)
    args = parser.parse_args()

    os.makedirs(CAPTURE_DIR, exist_ok=True)
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Viewer running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")


if __name__ == "__main__":
    main()
