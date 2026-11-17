"""Gmail integration via Gmail API (OAuth2).

Token is stored at ~/.gmail_token.json — generated once via scripts/gmail_auth.py.
Credentials (client_id, client_secret) are read from env vars or fall back to the
values stored in the token file itself.

No additional setup needed after the initial OAuth flow.
"""
from __future__ import annotations

import base64
import email as email_lib
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

TOKEN_PATH = Path.home() / ".gmail_token.json"

# Scopes required — must match what was used during initial OAuth
_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

_TOKEN_CACHE: dict = {}  # {access_token, expires_at, refresh_token, client_id, client_secret}


def _load_token_file() -> dict:
    """Load saved OAuth token from ~/.gmail_token.json."""
    if not TOKEN_PATH.exists():
        raise EnvironmentError(
            f"Gmail token not found at {TOKEN_PATH}. "
            "Run: python3 scripts/gmail_auth.py"
        )
    return json.loads(TOKEN_PATH.read_text())


def _save_token_file(data: dict) -> None:
    TOKEN_PATH.write_text(json.dumps(data, indent=2))


def _gmail_access_token() -> str:
    """Return a valid Gmail access token, refreshing if expired."""
    global _TOKEN_CACHE

    now = time.time()
    if _TOKEN_CACHE.get("access_token") and now < _TOKEN_CACHE.get("expires_at", 0) - 60:
        return _TOKEN_CACHE["access_token"]

    token_data = _load_token_file()

    # Check if stored token is still valid
    expiry = token_data.get("expiry", "")
    if expiry:
        # Google stores expiry as ISO format: "2026-09-07T06:00:00Z"
        try:
            from datetime import datetime, timezone
            exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            if exp_dt.timestamp() > now + 60:
                _TOKEN_CACHE = {
                    "access_token": token_data["token"],
                    "expires_at": exp_dt.timestamp(),
                    "refresh_token": token_data.get("refresh_token", ""),
                    "client_id": token_data.get("client_id", ""),
                    "client_secret": token_data.get("client_secret", ""),
                }
                return _TOKEN_CACHE["access_token"]
        except Exception:
            pass

    # Refresh using refresh_token
    refresh_token = token_data.get("refresh_token")
    client_id = token_data.get("client_id") or os.environ.get("GMAIL_CLIENT_ID")
    client_secret = token_data.get("client_secret") or os.environ.get("GMAIL_CLIENT_SECRET")

    if not refresh_token:
        raise EnvironmentError(
            "No refresh_token in Gmail token file. "
            "Re-run: python3 scripts/gmail_auth.py"
        )
    if not client_id or not client_secret:
        raise EnvironmentError(
            "Missing client_id/client_secret. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET env vars."
        )

    post_data = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=post_data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gmail token refresh failed: {exc.code} {exc.read().decode()}") from exc

    if "access_token" not in body:
        raise RuntimeError(f"Gmail token refresh error: {body}")

    expires_in = int(body.get("expires_in", 3600))
    _TOKEN_CACHE = {
        "access_token": body["access_token"],
        "expires_at":   now + expires_in,
        "refresh_token": refresh_token,
        "client_id":    client_id,
        "client_secret": client_secret,
    }

    # Update token file with new access_token + expiry
    from datetime import datetime, timezone, timedelta
    token_data["token"] = body["access_token"]
    token_data["expiry"] = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    _save_token_file(token_data)

    return _TOKEN_CACHE["access_token"]


def _gmail_request(method: str, path: str, payload: dict | None = None) -> dict:
    """Make an authenticated Gmail API call. Returns parsed JSON."""
    token = _gmail_access_token()
    url = f"https://gmail.googleapis.com{path}"
    body = json.dumps(payload).encode() if payload else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        raise RuntimeError(f"Gmail API {method} {path} → {exc.code}: {err_body}") from exc


def _decode_body(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text
    return ""


def _fmt_message(msg: dict, include_body: bool = False) -> dict:
    """Extract key fields from a raw Gmail message object."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    result = {
        "id":       msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "subject":  headers.get("subject", "(no subject)"),
        "from":     headers.get("from", ""),
        "to":       headers.get("to", ""),
        "date":     headers.get("date", ""),
        "snippet":  msg.get("snippet", ""),
        "labels":   msg.get("labelIds", []),
    }
    if include_body:
        result["body"] = _decode_body(msg.get("payload", {}))
    return result


def list_emails(
    query: str = "",
    max_results: int = 10,
    label: str = "INBOX",
    unread_only: bool = False,
) -> list[dict]:
    """List emails from Gmail with optional filters.

    Args:
        query:       Gmail search query (e.g. 'from:customer@example.com subject:incident').
                     Supports all Gmail search operators.
        max_results: Max emails to return (1–50). Default 10.
        label:       Gmail label to filter. Default 'INBOX'. Use 'SENT' for sent mail.
        unread_only: Only return unread emails. Default False.
        
    Returns list of email summaries (id, subject, from, date, snippet).
    """
    max_results = max(1, min(max_results, 50))
    q_parts = []
    if query:
        q_parts.append(query)
    if label and label != "INBOX":
        q_parts.append(f"label:{label.lower()}")
    elif label == "INBOX":
        q_parts.append("in:inbox")
    if unread_only:
        q_parts.append("is:unread")

    qs = urllib.parse.urlencode({
        "q":          " ".join(q_parts),
        "maxResults": str(max_results),
    })
    result = _gmail_request("GET", f"/gmail/v1/users/me/messages?{qs}")
    messages = result.get("messages", [])

    if not messages:
        return []

    # Fetch metadata for each message (parallel-style via sequential calls)
    emails = []
    for m in messages:
        try:
            msg = _gmail_request("GET", f"/gmail/v1/users/me/messages/{m['id']}?format=metadata"
                                        "&metadataHeaders=Subject&metadataHeaders=From"
                                        "&metadataHeaders=To&metadataHeaders=Date")
            emails.append(_fmt_message(msg))
        except Exception:
            emails.append({"id": m["id"], "error": "failed to fetch"})

    return emails


def get_email(message_id: str) -> dict:
    """Fetch full content of a Gmail message by ID, including body text.

    Args:
        message_id: Gmail message ID (from list_emails).

    Returns dict with subject, from, to, date, body, labels.
    """
    msg = _gmail_request("GET", f"/gmail/v1/users/me/messages/{message_id}?format=full")
    return _fmt_message(msg, include_body=True)


def send_email(
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: Optional[str] = None,
    html: bool = False,
    cc: Optional[str] = None,
) -> dict:
    """Send an email via Gmail.

    Args:
        to:                  Recipient email address(es), comma-separated.
        subject:             Email subject.
        body:                Plain text or HTML email body.
        reply_to_message_id: If replying, provide the original message ID to thread correctly.
        html:                If True, send as HTML email (text/html). Default False (text/plain).
        cc:                  Optional CC address(es), comma-separated.

    Returns dict with sent message id and thread_id.
    """
    # Build RFC 2822 message
    from_addr = "me"  # Gmail API 'me' resolves to authenticated user

    content_type = "text/html; charset=utf-8" if html else "text/plain; charset=utf-8"

    headers = [
        f"To: {to}",
        f"Subject: {subject}",
        f"Content-Type: {content_type}",
        "MIME-Version: 1.0",
    ]
    if cc:
        headers.insert(1, f"Cc: {cc}")

    thread_id = None
    if reply_to_message_id:
        # Get original message to extract thread_id and Message-ID header
        try:
            orig = _gmail_request("GET",
                f"/gmail/v1/users/me/messages/{reply_to_message_id}?format=metadata"
                "&metadataHeaders=Message-ID&metadataHeaders=Subject")
            thread_id = orig.get("threadId")
            orig_headers = {h["name"].lower(): h["value"]
                            for h in orig.get("payload", {}).get("headers", [])}
            if orig_headers.get("message-id"):
                headers.append(f"In-Reply-To: {orig_headers['message-id']}")
                headers.append(f"References: {orig_headers['message-id']}")
        except Exception:
            pass

    raw_message = "\r\n".join(headers) + "\r\n\r\n" + body
    encoded = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("utf-8")

    payload: dict = {"raw": encoded}
    if thread_id:
        payload["threadId"] = thread_id

    result = _gmail_request("POST", "/gmail/v1/users/me/messages/send", payload)
    return {
        "sent":      True,
        "id":        result.get("id", ""),
        "thread_id": result.get("threadId", ""),
        "to":        to,
        "subject":   subject,
    }

    thread_id = None
    if reply_to_message_id:
        # Get original message to extract thread_id and Message-ID header
        try:
            orig = _gmail_request("GET",
                f"/gmail/v1/users/me/messages/{reply_to_message_id}?format=metadata"
                "&metadataHeaders=Message-ID&metadataHeaders=Subject")
            thread_id = orig.get("threadId")
            orig_headers = {h["name"].lower(): h["value"]
                            for h in orig.get("payload", {}).get("headers", [])}
            if orig_headers.get("message-id"):
                headers.append(f"In-Reply-To: {orig_headers['message-id']}")
                headers.append(f"References: {orig_headers['message-id']}")
        except Exception:
            pass

    raw_message = "\r\n".join(headers) + "\r\n\r\n" + body
    encoded = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("utf-8")

    payload: dict = {"raw": encoded}
    if thread_id:
        payload["threadId"] = thread_id

    result = _gmail_request("POST", "/gmail/v1/users/me/messages/send", payload)
    return {
        "sent":      True,
        "id":        result.get("id", ""),
        "thread_id": result.get("threadId", ""),
        "to":        to,
        "subject":   subject,
    }



def send_email_with_attachments(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    cc: str | None = None,
    html: bool = False,
) -> dict:
    """Send email with optional CC and file attachments via Gmail API.

    Args:
        to:          Recipient(s), comma-separated.
        subject:     Email subject.
        body:        Plain text or HTML body.
        attachments: List of file paths to attach.
        cc:          CC address(es), comma-separated.
        html:        If True, body is sent as text/html.

    Returns dict with sent status, id, thread_id.
    """
    import email as _email
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email.mime.application import MIMEApplication
    from email import encoders
    import mimetypes, os

    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    for filepath in (attachments or []):
        filepath = os.path.expanduser(filepath)
        if not os.path.exists(filepath):
            continue
        mime_type, _ = mimetypes.guess_type(filepath)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        with open(filepath, "rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(filepath),
            )
            msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = _gmail_request("POST", "/gmail/v1/users/me/messages/send", {"raw": raw})
    return {
        "sent":      True,
        "id":        result.get("id", ""),
        "thread_id": result.get("threadId", ""),
        "to":        to,
        "cc":        cc or "",
        "subject":   subject,
        "attachments": [os.path.basename(a) for a in (attachments or [])],
    }

def mark_email_read(message_id: str) -> dict:
    """Mark a Gmail message as read (remove UNREAD label).

    Args:
        message_id: Gmail message ID.
    """
    _gmail_request("POST", f"/gmail/v1/users/me/messages/{message_id}/modify",
                   {"removeLabelIds": ["UNREAD"]})
    return {"message_id": message_id, "marked_read": True}


def search_emails_from_customer(customer_email: str, max_results: int = 10) -> list[dict]:
    """Search Gmail for emails from a specific customer email address.

    Convenience wrapper around list_emails for the common ops use-case of
    checking if a customer sent anything related to an incident or request.

    Args:
        customer_email: Customer's email address to search for.
        max_results:    Max results to return. Default 10.
    """
    return list_emails(query=f"from:{customer_email}", max_results=max_results)
