"""GitLab MR reviewer bot: one note, then Approve or unapprove."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from check_packages import is_exact_pin, load_allowlist, pep503

ROOT = Path(__file__).resolve().parents[2]

BLOCKING_JOBS = ("backend", "frontend", "quality", "build", "security:node")
JOB_ALIASES = {
    "security-node": "security:node",
    "security_node": "security:node",
    "node-audit": "security:node",
    "security-pip": "security:pip",
    "security_pip": "security:pip",
    "pip-audit": "security:pip",
}
PASS_STATUSES = {"success", "passed", "ok"}
PIN_FILES = (
    "backend/requirements.txt",
    "backend/requirements-dev.txt",
    "frontend/package.json",
    "approved-packages.json",
    "docs/approved-packages.md",
)
CHROME_ROOTS = ("frontend/src/",)
JSON_PIN_RE = re.compile(r'["\']([^"\']+)["\']\s*:\s*["\']([^"\']+)["\']')
REQ_PIN_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*([<>=!~][^;#]+)?")
PY_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)")
JS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
JS_ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^;]*?\)|[A-Za-z_$][\w$]*)\s*=>"
)
VERSION_SPEC_RE = re.compile(r"^(?:\^|~|==|!=|<=|>=|<|>)?\d")
SKIP_JSON_KEYS = {
    "name",
    "version",
    "private",
    "type",
    "scripts",
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
    "note",
    "backend",
    "frontend",
    "description",
    "license",
    "main",
    "module",
    "exports",
    "files",
    "author",
    "repository",
}
FIVE_PARTS = ("what", "why", "who", "where", "how")
VERDICT_LABELS = {
    "dry-run": "DRY-RUN",
    "missing-token": "MISSING-TOKEN",
    "approve": "APPROVE",
    "hold": "HOLD",
    "unapprove": "UNAPPROVE",
}


def is_mr_context(env=None):
    """
    What: True when GitLab has attached a merge request IID.
    Why: The bot only talks to the API on a real MR pipeline.
    Who: is_dry_run, decide, and run_review.
    Where: CI_MERGE_REQUEST_IID on the hosted review job.
    How: Read the env mapping and treat any non-empty IID as MR context.
    """
    data = os.environ if env is None else env
    return bool(str(data.get("CI_MERGE_REQUEST_IID") or "").strip())


def is_dry_run(env=None):
    """
    What: True for a laptop run or when REVIEW_DRY_RUN is an explicit yes.
    Why: Hosted Approve must never fire from a local checkout by accident.
    Who: run_review before it chooses the API path.
    Where: REVIEW_DRY_RUN plus the merge-request IID check.
    How: Treat 1/true/yes as dry-run, and also dry-run when this is not an MR.
    """
    data = os.environ if env is None else env
    flag = str(data.get("REVIEW_DRY_RUN") or "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    return not is_mr_context(data)


def setup_steps():
    """
    What: The four GitLab setup lines a missing token must print.
    Why: A red review job should teach the operator instead of faking Approve.
    Who: run_review when an MR has no GITLAB_REVIEWER_TOKEN.
    Where: stderr on the hosted review job.
    How: Name the Project Access Token, api scope, masked variable, and reviewer.
    """
    return "\n".join(
        [
            "GitLab MR reviewer setup failed closed. It never fakes an Approve.",
            "1. Create a GitLab Project Access Token with the api scope and a role that can approve merge requests (Developer or Maintainer).",
            "2. Add a masked CI/CD variable named GITLAB_REVIEWER_TOKEN.",
            "3. Add that project-bot user as an eligible (and required, if you want the wait gone) MR reviewer under Settings → Merge requests.",
            "A missing GITLAB_REVIEWER_TOKEN fails this job. Do not invent a token or skip the Approve call.",
        ]
    )


def evaluate_jobs(jobs):
    """
    What: Grade this pipeline's jobs against the product gates.
    Why: pip-audit may stay red; node-audit and the four product jobs may not.
    Who: run_review after it fetches /pipelines/:id/jobs.
    Where: BLOCKING_JOBS plus the security:pip exception.
    How: Alias names, require each blocker present and passing, and ignore pip.
    """
    seen = {}
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        raw = str(job.get("name") or "").strip()
        name = JOB_ALIASES.get(raw, raw)
        status = str(job.get("status") or "").strip().lower()
        if name:
            seen[name] = status
    lines = []
    ok = True
    for name in BLOCKING_JOBS:
        status = seen.get(name)
        if not status:
            lines.append(f"{name}: missing")
            ok = False
        elif status in PASS_STATUSES:
            lines.append(f"{name}: {status}")
        else:
            lines.append(f"{name}: {status} — hold")
            ok = False
    if "security:pip" in seen:
        status = seen["security:pip"]
        lines.append(f"security:pip / pip-audit: {status} (does not block)")
    return ok, lines


def parse_diff(text):
    """
    What: Split a unified diff into file records with the b/ path and added lines.
    Why: Finding scanners need one path plus the + lines, not a raw blob.
    Who: scan_diff and the parse_diff path test.
    Where: git diff output or GitLab changes[].diff strings.
    How: Cut on diff --git a/X b/Y, then prefer +++ b/ when that header appears.
    """
    files = []
    current = None
    for line in (text or "").splitlines():
        if line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            parts = line.split()
            path = ""
            if len(parts) >= 4:
                right = parts[3]
                path = right[2:] if right.startswith("b/") else right
            current = {"path": path, "added": [], "lines": []}
            continue
        if current is None:
            continue
        if line.startswith("+++ b/"):
            current["path"] = line[6:]
        current["lines"].append(line)
        if line.startswith("+") and not line.startswith("+++"):
            current["added"].append(line[1:])
    if current is not None:
        files.append(current)
    return files


def _is_pin_file(path):
    """
    What: True when this diff path is a pin manifest the bot must scan.
    Why: Caret ranges and extra names only matter in the declared pin files.
    Who: scan_diff when it walks each parsed file.
    Where: PIN_FILES relative to the repository root.
    How: Compare the posix path to each known manifest name.
    """
    rel = (path or "").replace("\\", "/").lstrip("./")
    return rel in PIN_FILES


def _is_chrome_file(path):
    """
    What: True when this path sits under a UI root the chrome locks cover.
    Why: title= and folder-frame CSS must not return on the docs reader.
    Who: scan_diff chrome checks.
    Where: CHROME_ROOTS, which is frontend/src/.
    How: Prefix-match the posix path against each chrome root.
    """
    rel = (path or "").replace("\\", "/").lstrip("./")
    return any(rel.startswith(root) for root in CHROME_ROOTS)


def _is_test_path(path):
    """
    What: True when this file lives under a tests directory.
    Why: Unit tests may add helpers without a production five-part comment.
    Who: The new-function scanner inside scan_diff.
    Where: Paths that contain /tests/.
    How: Normalize slashes and look for a tests segment.
    """
    rel = (path or "").replace("\\", "/").lstrip("./")
    return "/tests/" in f"/{rel}/" or rel.startswith("tests/")


def _kind_for_path(path):
    """
    What: Pick python or node pin rules from the file path.
    Why: ==X.Y.Z is exact for wheels; X.Y.Z without a caret is exact for npm.
    Who: The pin scanner inside scan_diff.
    Where: requirements files versus package.json and the allowlist doc.
    How: requirements and backend allowlist keys are python; the rest are node.
    """
    rel = (path or "").replace("\\", "/")
    if rel.endswith("requirements.txt") or rel.endswith("requirements-dev.txt"):
        return "python"
    if rel.endswith("package.json"):
        return "node"
    return ""


def _name_allowed(name, allow):
    """
    What: True when this package already sits on the committed allowlist.
    Why: A new first-party name must become a finding until the list grows.
    Who: The pin scanner inside scan_diff.
    Where: approved-packages.json backend and frontend maps.
    How: PEP 503 fold for Python names; exact key match for Node names.
    """
    backend = allow.get("backend") or {}
    frontend = allow.get("frontend") or {}
    if pep503(name) in backend:
        return True
    if name in frontend:
        return True
    folded = {item.lower(): item for item in frontend}
    return name.lower() in folded


def _looks_like_spec(spec):
    """
    What: True when a JSON value looks like a version specifier.
    Why: package.json also holds true/portal strings that are not pins.
    Who: The pin scanner when it reads "name": "spec" lines.
    Where: Added lines in PIN_FILES.
    How: Accept a leading comparator or caret/tilde, then a digit.
    """
    return bool(VERSION_SPEC_RE.match((spec or "").strip()))


def _pin_findings(path, added, allow):
    """
    What: Findings for inexact pins and names missing from the allowlist.
    Why: The bot must fail a caret react pin and a new requests line.
    Who: scan_diff for each pin-file hunk.
    Where: Added lines only, never the whole committed manifest.
    How: Parse requirement and JSON pairs, then is_exact_pin plus the allowlist.
    """
    findings = []
    kind_hint = _kind_for_path(path)
    for row in added:
        stripped = row.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-r "):
            continue
        pairs = []
        json_hit = JSON_PIN_RE.search(row)
        if json_hit:
            key, spec = json_hit.group(1), json_hit.group(2)
            if key not in SKIP_JSON_KEYS and _looks_like_spec(spec):
                kind = kind_hint or ("python" if spec.strip().startswith("==") else "node")
                pairs.append((key, spec, kind))
        elif kind_hint == "python" or REQ_PIN_RE.match(stripped):
            match = REQ_PIN_RE.match(stripped)
            if match and (kind_hint == "python" or _looks_like_spec(match.group(2) or "")):
                spec = (match.group(2) or "").strip()
                pairs.append((match.group(1), spec, "python"))
        for name, spec, kind in pairs:
            if spec and not is_exact_pin(spec, kind):
                findings.append(f"{path}: {name} specifier {spec!r} is not an exact pin")
            if not _name_allowed(name, allow):
                findings.append(f"{path}: {name} is not on the approved list")
    return findings


def _chrome_findings(path, added):
    """
    What: Findings for locked overlay chrome that must not return.
    Why: title= tooltips, flyouts, Hornet, DocsHero, and the 1180 folder frame.
    Who: scan_diff for files under frontend/src/.
    Where: Added CSS and JSX lines only.
    How: Search the joined added text for each forbidden marker.
    """
    blob = "\n".join(added)
    findings = []
    if re.search(r"title\s*=", blob):
        findings.append(f"{path}: title= tooltip chrome is locked out")
    if re.search(r"data-flyout|flyout\.css|annotateProseLinks|\bflyout\b", blob, re.I):
        findings.append(f"{path}: flyout chrome is locked out")
    if "Hornet" in blob:
        findings.append(f"{path}: Hornet animation chrome is locked out")
    if "DocsHero" in blob:
        findings.append(f"{path}: DocsHero photo band is locked out")
    if re.search(r"clip-path\s*:[^;]*polygon|clip-path\s+polygon", blob, re.I):
        findings.append(f"{path}: clip-path folder frame is locked out")
    if re.search(r"min\(\s*1180px|width[^;]*1180|1180px", blob, re.I):
        findings.append(f"{path}: width min(1180px) folder frame is locked out")
    return findings


def _has_five_part(text):
    """
    What: True when a snippet names What, Why, Who, Where, and How.
    Why: A new function without that house comment is a hold finding.
    Who: The new-function scanner inside scan_diff.
    Where: Added lines near a new def or JS function.
    How: Case-fold the snippet and require each of the five labels.
    """
    lower = (text or "").lower()
    return all(part in lower for part in FIVE_PARTS)


def _comment_findings(path, added):
    """
    What: Findings for newly added functions that lack a five-part comment.
    Why: The quality gate expects What/Why/Who/Where/How on every new helper.
    Who: scan_diff for first-party source, skipping /tests/.
    Where: Added def, function, and const-arrow lines.
    How: Take a window of nearby added lines and look for the five labels.
    """
    if _is_test_path(path):
        return []
    findings = []
    for idx, row in enumerate(added):
        name = None
        match = PY_DEF_RE.match(row)
        if match:
            name = match.group(1)
        if name is None:
            match = JS_FUNC_RE.match(row)
            if match:
                name = match.group(1)
        if name is None:
            match = JS_ARROW_RE.match(row)
            if match:
                name = match.group(1)
        if not name:
            continue
        window = added[max(0, idx - 8) : idx + 16]
        if not _has_five_part("\n".join(window)):
            findings.append(f"{path}: {name} is missing a five-part comment")
    return findings


def scan_diff(files, allow=None):
    """
    What: Turn a parsed (or raw) diff into blocking reviewer findings.
    Why: Pins, allowlist names, overlay chrome, and missing comments hold an MR.
    Who: run_review on the local git diff or the GitLab changes payload.
    Where: PIN_FILES, frontend/src/, and new functions outside /tests/.
    How: Load the allowlist when omitted, then run the pin, chrome, and comment scanners.
    """
    if isinstance(files, str):
        files = parse_diff(files)
    if allow is None:
        allow = load_allowlist(ROOT / "approved-packages.json")
    findings = []
    for item in files or []:
        path = str(item.get("path") or "")
        added = list(item.get("added") or [])
        if _is_pin_file(path):
            findings.extend(_pin_findings(path, added, allow))
        if _is_chrome_file(path):
            findings.extend(_chrome_findings(path, added))
        findings.extend(_comment_findings(path, added))
    return findings


def decide(is_mr, token, jobs_ok, findings, was_approved):
    """
    What: Pick dry-run, missing-token, approve, unapprove, or hold.
    Why: The note and the API call must share one verdict word.
    Who: run_review after jobs and findings are known.
    Where: Token presence, job ok, findings list, and prior approval.
    How: Missing token first, then dry-run, then approve, then unapprove, else hold.
    """
    if is_mr and not str(token or "").strip():
        return "missing-token"
    if not is_mr:
        return "dry-run"
    if jobs_ok and not findings:
        return "approve"
    if was_approved:
        return "unapprove"
    return "hold"


def build_note(verdict, pipeline_lines, findings, action):
    """
    What: Markdown MR note with verdict, pipeline, findings, and action.
    Why: Operators should see one note, not a thread of status chatter.
    Who: run_review when it prints a dry-run or POSTs /notes.
    Where: The GitLab merge request discussion.
    How: Render ## Reviewer bot plus the four section headings the tests read.
    """
    pipe = "\n".join(f"- {line}" for line in (pipeline_lines or []) ) or "- (none)"
    found = "\n".join(f"- {item}" for item in (findings or [])) or "- none"
    return "\n".join(
        [
            "## Reviewer bot",
            f"**Verdict:** {verdict}",
            "",
            "### Pipeline",
            pipe,
            "",
            "### Findings",
            found,
            "",
            "### Action",
            action,
        ]
    )


def gitlab_curl(method, url, token, body=None):
    """
    What: One GitLab REST call using python3 plus curl, no extra HTTP library.
    Why: The hosted job image is python:3.12 and only adds curl and make.
    Who: run_review when the caller does not inject curl_fn.
    Where: CI_API_V4_URL project routes with a PRIVATE-TOKEN header.
    How: Invoke curl, write the JSON body when present, and split out the status.
    """
    cmd = [
        "curl",
        "-sS",
        "-X",
        method,
        "-H",
        f"PRIVATE-TOKEN: {token}",
        "-H",
        "Accept: application/json",
        "-w",
        "\n%{http_code}",
    ]
    if body is not None:
        cmd.extend(
            [
                "-H",
                "Content-Type: application/json",
                "--data-binary",
                json.dumps(body),
            ]
        )
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return 0, {}
    raw = proc.stdout or ""
    if "\n" in raw:
        payload_text, status_text = raw.rsplit("\n", 1)
    else:
        payload_text, status_text = raw, "0"
    try:
        status = int(status_text.strip() or "0")
    except ValueError:
        status = 0
    payload_text = payload_text.strip()
    if not payload_text:
        return status, {}
    try:
        return status, json.loads(payload_text)
    except json.JSONDecodeError:
        return status, {"raw": payload_text}


def _local_diff():
    """
    What: Working-tree plus index unified diff for a laptop dry-run.
    Why: make review on a checkout has no GitLab changes endpoint.
    Who: run_review on the dry-run path.
    Where: git diff HEAD and git diff --cached from ROOT.
    How: Concatenate both command outputs; empty string when git is missing.
    """
    chunks = []
    for args in (["git", "diff", "HEAD"], ["git", "diff", "--cached"]):
        try:
            proc = subprocess.run(
                args,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        chunks.append(proc.stdout or "")
    return "".join(chunks)


def _changes_text(payload):
    """
    What: Join GitLab change diffs into one parse_diff blob.
    Why: The changes API returns objects, not a raw git patch.
    Who: run_review after GET /merge_requests/:iid/changes.
    Where: payload.changes[].diff, or a list of those objects.
    How: Walk dict or list shapes and concatenate each diff string.
    """
    changes = []
    if isinstance(payload, dict):
        changes = payload.get("changes") or payload.get("diffs") or []
    elif isinstance(payload, list):
        changes = payload
    texts = []
    for item in changes:
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict):
            texts.append(item.get("diff") or "")
    return "\n".join(texts)


def _jobs_payload(payload):
    """
    What: Normalize a jobs response to a list of {name, status} dicts.
    Why: Tests return a bare list; GitLab may wrap the same rows.
    Who: run_review after GET /pipelines/:id/jobs.
    Where: The JSON array or a dict with a jobs key.
    How: Prefer a list payload, else payload.jobs, else an empty list.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("jobs") or payload.get("data") or []
        if isinstance(rows, list):
            return rows
    return []


def _was_approved(payload):
    """
    What: True when this MR already has an approval recorded.
    Why: A later red push must unapprove instead of silently holding.
    Who: run_review after GET /merge_requests/:iid/approvals.
    Where: The GitLab approvals payload.
    How: Read the approved boolean, else treat a non-empty approved_by as yes.
    """
    if not isinstance(payload, dict):
        return False
    if "approved" in payload:
        return bool(payload.get("approved"))
    return bool(payload.get("approved_by") or [])


def _project_base(env):
    """
    What: GitLab /projects/:id prefix for every reviewer API call.
    Why: Notes, jobs, and approvals all hang off the same project URL.
    Who: run_review when it builds the live endpoints.
    Where: CI_API_V4_URL plus a URL-encoded CI_PROJECT_ID.
    How: Strip a trailing slash on the API root and quote the project id.
    """
    api = str(env.get("CI_API_V4_URL") or "https://gitlab.com/api/v4").rstrip("/")
    project = quote(str(env.get("CI_PROJECT_ID") or ""), safe="")
    return f"{api}/projects/{project}"


def _action_text(verdict):
    """
    What: One-line action sentence for the MR note.
    Why: The Action section should say what the bot did, not only the verdict word.
    Who: run_review when it calls build_note.
    Where: The ### Action block.
    How: Map approve/hold/unapprove/dry-run onto a fixed sentence.
    """
    if verdict == "approve":
        return "Posting one note and Approving this merge request."
    if verdict == "unapprove":
        return "Posting one note and unapproving because a later push failed a product gate."
    if verdict == "hold":
        return "Holding. Not approving this merge request."
    if verdict == "dry-run":
        return "Would not call the GitLab API. Local dry-run only."
    return "Stopping. Missing GITLAB_REVIEWER_TOKEN; never faking an Approve."


def run_review(env=None, curl_fn=None):
    """
    What: Run the reviewer: dry-run locally, or note plus Approve on a GitLab MR.
    Why: make review and the hosted job must share one helper and one verdict.
    Who: scripts/review-mr.sh and the unit tests that inject curl_fn.
    Where: Local git diff, or GitLab changes/jobs/approvals/notes/approve.
    How: Fail closed without a token; dry-run prints a note; live path POSTs once.
    """
    data = os.environ if env is None else env
    token = str(data.get("GITLAB_REVIEWER_TOKEN") or "").strip()
    mr = is_mr_context(data)
    dry = is_dry_run(data)
    if mr and not token and not dry:
        print(setup_steps(), file=sys.stderr)
        return 1
    if dry:
        findings = scan_diff(parse_diff(_local_diff()))
        note = build_note(
            "DRY-RUN",
            ["(dry-run: no pipeline jobs)"],
            findings,
            _action_text("dry-run"),
        )
        print(note)
        return 0
    request = curl_fn or gitlab_curl
    base = _project_base(data)
    iid = quote(str(data.get("CI_MERGE_REQUEST_IID") or ""), safe="")
    pipeline = quote(str(data.get("CI_PIPELINE_ID") or ""), safe="")
    mr_root = f"{base}/merge_requests/{iid}"
    changes_payload = request("GET", f"{mr_root}/changes", token)[1]
    jobs_payload = request(
        "GET",
        f"{base}/pipelines/{pipeline}/jobs?per_page=100",
        token,
    )[1]
    approvals_payload = request("GET", f"{mr_root}/approvals", token)[1]
    findings = scan_diff(parse_diff(_changes_text(changes_payload)))
    jobs_ok, job_lines = evaluate_jobs(_jobs_payload(jobs_payload))
    was_approved = _was_approved(approvals_payload)
    verdict = decide(mr, token, jobs_ok, findings, was_approved)
    note = build_note(
        VERDICT_LABELS.get(verdict, verdict.upper()),
        job_lines,
        findings,
        _action_text(verdict),
    )
    request("POST", f"{mr_root}/notes", token, {"body": note})
    if verdict == "approve":
        request("POST", f"{mr_root}/approve", token)
        print(note)
        return 0
    if verdict == "unapprove":
        request("POST", f"{mr_root}/unapprove", token)
        print(note)
        return 1
    print(note)
    return 1


def main(argv=None):
    """
    What: CLI entry that honors --dry-run then calls run_review.
    Why: make review and sh scripts/review-mr.sh --dry-run share this process.
    Who: The review-mr.sh wrapper.
    Where: sys.argv, copying os.environ so --dry-run cannot leak into the parent.
    How: Set REVIEW_DRY_RUN=1 when --dry-run is present, then exit with run_review.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    data = dict(os.environ)
    if "--dry-run" in args:
        data["REVIEW_DRY_RUN"] = "1"
    return run_review(data)


if __name__ == "__main__":
    raise SystemExit(main())
