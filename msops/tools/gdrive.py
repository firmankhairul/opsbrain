# -*- coding: utf-8 -*-
"""
Google Drive MCP tools — ms-ops integration
Reuses the same OAuth token as gmail.py (~/.gmail_token.json).

Available functions:
    list_drive_files(query, folder_id, max_results)  — search/list files
    get_drive_file(file_id)                           — get file metadata
    read_drive_file(file_id)                          — read text/doc content
    upload_drive_file(name, content, folder_id, mime_type) — upload/create file
    list_drive_folders(parent_id)                     — list folders
"""

import json
import os
import io
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

TOKEN_PATH = os.path.expanduser("~/.gmail_token.json")

# ──────────────────────────────────────────────────────────────────────────────
# Auth helpers (reuse Gmail token)
# ──────────────────────────────────────────────────────────────────────────────

def _drive_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(
            "Google OAuth token not found. Run scripts/gmail_auth.py first."
        )
    data = json.loads(Path(TOKEN_PATH).read_text())
    refresh_token = data.get("refresh_token")
    client_id = data.get("client_id")
    client_secret = data.get("client_secret")

    if not refresh_token:
        raise RuntimeError("No refresh_token in token file. Re-run gmail_auth.py.")

    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Drive token refresh failed: {exc.code} {exc.read().decode()}"
        ) from exc


def _drive_request(method: str, path: str, payload: dict | None = None,
                   params: dict | None = None) -> dict:
    """Make an authenticated Drive API call."""
    token = _drive_access_token()
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"https://www.googleapis.com{path}{qs}"
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        raise RuntimeError(
            f"Drive API {method} {path} → {exc.code}: {err_body}"
        ) from exc


def _drive_download(file_id: str, token: str) -> bytes:
    """Download raw file bytes."""
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

# ──────────────────────────────────────────────────────────────────────────────
# Public tools
# ──────────────────────────────────────────────────────────────────────────────

def list_drive_files(
    query: str = "",
    folder_id: str = "",
    max_results: int = 20,
) -> list[dict]:
    """
    List/search files in Google Drive.

    Args:
        query:      Drive query string, e.g. "name contains 'PoM'" or free text
        folder_id:  Limit results to a specific folder ID
        max_results: Max number of results to return

    Returns list of dicts with: id, name, mimeType, modifiedTime, size, webViewLink
    """
    q_parts = []
    if query:
        q_parts.append(f"fullText contains '{query}' or name contains '{query}'")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    q_parts.append("trashed = false")

    params = {
        "q": " and ".join(q_parts),
        "pageSize": min(max_results, 100),
        "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink,parents)",
        "orderBy": "modifiedTime desc",
    }

    data = _drive_request("GET", "/drive/v3/files", params=params)
    files = data.get("files", [])
    return files


def list_drive_folders(parent_id: str = "root") -> list[dict]:
    """
    List folders inside a parent folder.

    Args:
        parent_id: Parent folder ID (default: 'root')

    Returns list of dicts with: id, name, modifiedTime, webViewLink
    """
    params = {
        "q": f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        "pageSize": 50,
        "fields": "files(id,name,modifiedTime,webViewLink)",
        "orderBy": "name",
    }
    data = _drive_request("GET", "/drive/v3/files", params=params)
    return data.get("files", [])


def get_drive_file(file_id: str) -> dict:
    """
    Get metadata of a specific file.

    Args:
        file_id: Google Drive file ID

    Returns dict with file metadata.
    """
    params = {
        "fields": "id,name,mimeType,modifiedTime,size,webViewLink,parents,description"
    }
    return _drive_request("GET", f"/drive/v3/files/{file_id}", params=params)


def read_drive_file(file_id: str) -> str:
    """
    Read the text content of a Drive file.
    Supports: plain text, Google Docs (exported as text), CSV.
    For Google Docs/Sheets/Slides, exports as plain text.

    Args:
        file_id: Google Drive file ID

    Returns file content as string (truncated to 50KB).
    """
    token = _drive_access_token()

    # Get mime type first
    meta = get_drive_file(file_id)
    mime = meta.get("mimeType", "")

    # Google Workspace files — export as plain text
    export_map = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    if mime in export_map:
        export_mime = export_map[mime]
        url = (f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
               f"?mimeType={urllib.parse.quote(export_mime)}")
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Drive read {file_id} → {exc.code}: {exc.read().decode()}"
        ) from exc

    # Decode and truncate
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return f"[binary file, {len(content)} bytes — cannot display as text]"

    if len(text) > 50000:
        text = text[:50000] + f"\n\n[...truncated, total {len(text)} chars]"
    return text


def upload_drive_file(
    name: str,
    content: str,
    folder_id: str = "",
    mime_type: str = "text/plain",
) -> dict:
    """
    Upload/create a new text file in Google Drive.

    Args:
        name:      File name
        content:   Text content to upload
        folder_id: Target folder ID (optional, defaults to root)
        mime_type: MIME type (default: text/plain)

    Returns dict with: id, name, webViewLink
    """
    token = _drive_access_token()

    # Build multipart upload
    metadata = {"name": name, "mimeType": mime_type}
    if folder_id:
        metadata["parents"] = [folder_id]

    boundary = "boundary_ms_ops_gdrive"
    meta_part = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
    )
    media_part = (
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--"
    )
    body = (meta_part + media_part).encode("utf-8")

    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", f"multipart/related; boundary={boundary}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Drive upload failed: {exc.code} {exc.read().decode()}"
        ) from exc
