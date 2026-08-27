"""Auth-gated Doxygen HTML proxy (S3 public URL, private S3, or local mock).

Never returns AWS credentials. The browser only talks to /api/docs/*.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen

from flask import Response, jsonify

ROOT = Path(__file__).resolve().parent
MOCK_HTML = ROOT / "doxygen-mock" / "html"

ALLOWED_EXT = {
    ".html",
    ".css",
    ".js",
    ".png",
    ".svg",
    ".gif",
    ".jpg",
    ".jpeg",
    ".woff",
    ".woff2",
    ".ico",
    ".map",
    ".md",
}

MIME_FALLBACK = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ico": "image/x-icon",
    ".map": "application/json",
    ".md": "text/markdown; charset=utf-8",
}

MAX_BYTES = 15 * 1024 * 1024
DEFAULT_TITLE = "F/A-18 Mission Software"


def _env(name: str, default: str = "") -> str:
    """
    What: Read a stripped environment variable.
    Why: Docs source is configured like SIGNUP_NOTIFY_EMAIL — env, not code.
    Who: docs_config and fetch helpers.
    Where: Process environment of the Flask app (backend/.env via load_dotenv).
    How: os.environ.get, strip whitespace, fall back to default.
    """
    return (os.environ.get(name) or default).strip()


def docs_config() -> dict:
    """
    What: Resolve which Doxygen source is active and how to reach it.
    Why: Public URL, private bucket, and mock are mutually preferred in that order.
    Who: meta_payload, fetch_doc, register_docs.
    Where: S3_DOXYGEN_* env vars; mock tree at backend/doxygen-mock/html.
    How: Prefer S3_DOXYGEN_BASE_URL, else bucket+region, else local mock.
    """
    base = _env("S3_DOXYGEN_BASE_URL").rstrip("/")
    bucket = _env("S3_DOXYGEN_BUCKET")
    prefix = _env("S3_DOXYGEN_PREFIX", "html").strip("/")
    region = _env("S3_DOXYGEN_REGION", "us-east-1") or "us-east-1"
    if base:
        source = "s3-public"
    elif bucket:
        source = "s3"
    else:
        source = "mock"
    return {
        "base_url": base,
        "bucket": bucket,
        "prefix": prefix,
        "region": region,
        "source": source,
        "configured": source != "mock",
    }


def docs_title() -> str:
    """
    What: Title string for /api/docs/meta.
    Why: The reader chrome and tab should name the document set.
    Who: meta_payload.
    Where: copy.json docs.title, else DEFAULT_TITLE.
    How: Import get_copy from the local copy module; swallow failures.
    """
    try:
        from copy_text import get_copy

        docs = (get_copy() or {}).get("docs") or {}
        text = str(docs.get("title") or "").strip()
        if text:
            return text
    except Exception:
        pass
    return DEFAULT_TITLE


def mime_for(rel_path: str) -> str:
    """
    What: Pick a Content-Type for a documentation object.
    Why: The browser must style CSS, run fonts, and render images correctly.
    Who: fetch_mock and the proxy response builder.
    Where: Extension of the sanitized relative path.
    How: MIME_FALLBACK first, then mimetypes.guess_type.
    """
    ext = Path(rel_path).suffix.lower()
    if ext in MIME_FALLBACK:
        return MIME_FALLBACK[ext]
    guessed, _ = mimetypes.guess_type(rel_path)
    return guessed or "application/octet-stream"


def normalize_doc_path(raw: str | None) -> str | None:
    """
    What: Turn a request path into a safe relative object key.
    Why: Denied users never see docs; granted users must not walk off the tree.
    Who: docs_proxy before any fetch.
    Where: GET /api/docs/<path> (empty means index.html).
    How: Unquote, reject NUL/backslash/.. /absolute, allowlist the extension.
    """
    text = unquote(raw or "").replace("\\", "/").strip()
    if "\x00" in text:
        return None
    text = text.lstrip("/")
    if not text or text.endswith("/"):
        text = (text.rstrip("/") + "/index.html").lstrip("/")
        if text == "index.html" and not (raw or "").strip():
            text = "index.html"
    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts:
        parts = ["index.html"]
    rel = "/".join(parts)
    ext = Path(rel).suffix.lower()
    if ext not in ALLOWED_EXT:
        return None
    return rel


def object_key(rel_path: str, prefix: str) -> str:
    """
    What: Build the S3 object key (or public URL tail) for a relative doc path.
    Why: Published Doxygen lives under html/ (or a custom prefix) in the bucket.
    Who: fetch_s3.
    Where: prefix from S3_DOXYGEN_PREFIX plus the sanitized relative path.
    How: Join prefix/rel_path, omitting an empty prefix.
    """
    if prefix:
        return f"{prefix}/{rel_path}"
    return rel_path


def fetch_mock(rel_path: str) -> tuple[bytes, str] | None:
    """
    What: Read a file from the bundled mock Doxygen tree.
    Why: The reader must work when no S3 bucket is configured.
    Who: fetch_doc when source is mock.
    Where: backend/doxygen-mock/html.
    How: Resolve under MOCK_HTML and refuse any path that escapes the root.
    """
    root = MOCK_HTML.resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not target.is_file():
        return None
    data = target.read_bytes()
    if len(data) > MAX_BYTES:
        return None
    return data, mime_for(rel_path)


def fetch_public(rel_path: str, base_url: str, prefix: str) -> tuple[bytes, str] | None:
    """
    What: HTTP-GET a Doxygen object from a public base URL (typically S3 website/REST).
    Why: Operators can point at a public html/ prefix without AWS keys.
    Who: fetch_doc when S3_DOXYGEN_BASE_URL is set.
    Where: base_url + / + rel_path (base already includes html/ if configured that way).
    How: urljoin the sanitized path; 20s timeout; honor Content-Type when present.
    """
    base = base_url.rstrip("/")
    if prefix and not base.endswith("/" + prefix) and not base.endswith(prefix):
        base = f"{base}/{prefix}"
    url = urljoin(base + "/", rel_path)
    req = Request(url, headers={"User-Agent": "f18-okta-portal-docs/1.0"})
    try:
        with urlopen(req, timeout=20) as resp:
            data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return None
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
            return data, ctype or mime_for(rel_path)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except URLError:
        raise


def _s3_client(region: str):
    """
    What: Build a boto3 S3 client from the process environment.
    Why: Private buckets need signed GetObject; keys stay on the server.
    Who: fetch_s3.
    Where: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / default credential chain.
    How: Import boto3 lazily; client(region_name=region) with no explicit keys.
    """
    import boto3

    return boto3.client("s3", region_name=region)


def fetch_s3(rel_path: str, bucket: str, prefix: str, region: str) -> tuple[bytes, str] | None:
    """
    What: GetObject a Doxygen file from a private S3 bucket.
    Why: Program docs may not be world-readable; the portal is the auth gate.
    Who: fetch_doc when a bucket is set and no public base URL is set.
    Where: s3://bucket/prefix/rel_path in S3_DOXYGEN_REGION.
    How: boto3 get_object; map 404/NoSuchKey to None; other errors propagate.
    """
    from botocore.exceptions import ClientError

    key = object_key(rel_path, prefix)
    client = _s3_client(region)
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"]
        data = body.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        ctype = (obj.get("ContentType") or "").split(";")[0].strip()
        return data, ctype or mime_for(rel_path)
    except ClientError as exc:
        code = (exc.response.get("Error") or {}).get("Code") or ""
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def fetch_doc(rel_path: str) -> tuple[bytes, str] | None:
    """
    What: Load one allowlisted documentation object from the active source.
    Why: One call site for mock, public URL, and private S3.
    Who: docs_proxy after path + clearance checks.
    Where: Source chosen by docs_config().
    How: s3-public → fetch_public; s3 → fetch_s3; else fetch_mock.
    """
    cfg = docs_config()
    if cfg["source"] == "s3-public":
        return fetch_public(rel_path, cfg["base_url"], cfg["prefix"])
    if cfg["source"] == "s3":
        return fetch_s3(rel_path, cfg["bucket"], cfg["prefix"], cfg["region"])
    return fetch_mock(rel_path)


def meta_payload() -> dict:
    """
    What: JSON body for GET /api/docs/meta.
    Why: The reader needs a title and source hint without any credentials.
    Who: docs_meta.
    Where: Configured source plus docs.title.
    How: {configured, source, title} only — never keys or bucket names that leak.
    """
    cfg = docs_config()
    return {
        "configured": bool(cfg["configured"]),
        "source": cfg["source"],
        "title": docs_title(),
    }


def require_granted(session_user_fn: Callable[[], dict | None]):
    """
    What: Enforce a logged-in session whose clearance is granted.
    Why: Denied and logged-out users must never see documentation bytes.
    Who: docs_meta and docs_proxy.
    Where: Flask session via the app's _session_user.
    How: 401 if no user; 403 if clearance is not granted; else the user dict.
    """
    user = session_user_fn()
    if user is None:
        return None, (jsonify({"error": "Not authenticated."}), 401)
    if user.get("clearance") != "granted":
        return None, (jsonify({"error": "Not authorized."}), 403)
    return user, None


def register_docs(app, session_user_fn: Callable[[], dict | None]) -> None:
    """
    What: Attach GET /api/docs/meta and GET /api/docs/<path> to the Flask app.
    Why: Keep proxy logic out of app.py so mock Okta and signup stay untouched.
    Who: app.py after _session_user is defined.
    Where: /api/docs/* only; Vite proxies /api to Flask.
    How: Closure over session_user_fn; serve bytes with nosniff; JSON errors.
    """

    @app.get("/api/docs/meta")
    def docs_meta():
        """
        What: Return {configured, source, title} for the granted session.
        Why: The SPA decides how to label the reader without fetching HTML first.
        Who: frontend docsMeta; GET /api/docs/meta.
        Where: Auth-gated; 401/403 otherwise.
        How: require_granted then meta_payload().
        """
        _user, err = require_granted(session_user_fn)
        if err:
            return err
        return jsonify(meta_payload())

    @app.get("/api/docs")
    @app.get("/api/docs/")
    def docs_index():
        """
        What: Serve the default Doxygen index for a granted session.
        Why: /api/docs and /api/docs/ should land on index.html.
        Who: Browser/SPA fetching the tree root.
        Where: Same gate as docs_proxy.
        How: Delegate to docs_proxy with index.html.
        """
        return docs_proxy("index.html")

    @app.get("/api/docs/<path:doc_path>")
    def docs_proxy(doc_path: str):
        """
        What: Proxy one allowlisted Doxygen object (HTML, CSS, JS, image, font).
        Why: The browser must never talk to S3 directly or see AWS keys.
        Who: The fancy reader (pages + rewritten asset URLs).
        Where: GET /api/docs/<path>; default index.html; mock if unconfigured.
        How: require_granted, normalize_doc_path, fetch_doc, Response with MIME.
        """
        if doc_path == "meta":
            return docs_meta()
        _user, err = require_granted(session_user_fn)
        if err:
            return err
        rel = normalize_doc_path(doc_path)
        if rel is None:
            return jsonify({"error": "Invalid document path."}), 400
        try:
            found = fetch_doc(rel)
        except Exception as exc:
            return jsonify({"error": f"Documentation source failed: {exc}"}), 502
        if found is None:
            return jsonify({"error": "Document not found."}), 404
        data, ctype = found
        return Response(
            data,
            mimetype=ctype,
            headers={
                "Cache-Control": "private, max-age=60",
                "X-Content-Type-Options": "nosniff",
                "X-Docs-Source": docs_config()["source"],
            },
        )
