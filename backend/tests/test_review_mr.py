"""GitLab MR reviewer bot: dry-run, gates, findings, approve/unapprove."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_mr import (
    BLOCKING_JOBS,
    build_note,
    decide,
    evaluate_jobs,
    is_dry_run,
    is_mr_context,
    parse_diff,
    run_review,
    scan_diff,
    setup_steps,
)


def _hunk(path, *added):
    """
    What: Build a tiny unified diff that only adds the given lines.
    Why: Finding tests need a stable hunk without a real git checkout.
    Who: The scan_diff and parse_diff cases below.
    Where: Synthetic paths such as frontend/package.json and Docs.jsx.
    How: Emit diff --git plus +++ b/path and one + line per added row.
    """
    rows = list(added)
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        "@@ -0,0 +1,%d @@" % len(rows),
    ]
    for row in rows:
        lines.append("+" + row)
    return "\n".join(lines) + "\n"


def _jobs(backend="success", node="success", pip="success", **extra):
    """
    What: One GitLab-shaped job list covering every product gate.
    Why: evaluate_jobs and run_review tests share the same name/status shape.
    Who: Pipeline and approve/unapprove cases.
    Where: Fake curl payloads and evaluate_jobs inputs.
    How: backend/frontend/quality/build/security:node/security:pip, then extras.
    """
    rows = [
        {"name": "backend", "status": backend},
        {"name": "frontend", "status": extra.get("frontend", "success")},
        {"name": "quality", "status": extra.get("quality", "success")},
        {"name": "build", "status": extra.get("build", "success")},
        {"name": "security:node", "status": node},
        {"name": "security:pip", "status": pip},
    ]
    return rows


def _mr_env(token="tok"):
    """
    What: Hosted merge-request environment the live bot path reads.
    Why: run_review tests must not inherit a laptop token or IID.
    Who: Missing-token, approve, and unapprove cases.
    Where: CI_* plus GITLAB_REVIEWER_TOKEN when token is non-empty.
    How: Copy a small dict; omit the token key when the argument is empty.
    """
    env = {
        "CI_MERGE_REQUEST_IID": "12",
        "CI_PROJECT_ID": "42",
        "CI_PIPELINE_ID": "99",
        "CI_API_V4_URL": "https://gitlab.example/api/v4",
    }
    if token:
        env["GITLAB_REVIEWER_TOKEN"] = token
    return env


def _tails(calls):
    """
    What: Last path segment of each fake curl URL.
    Why: approve and unapprove both contain the letters approve.
    Who: The live-path tests that assert which endpoint was hit.
    Where: The (method, url, token, body) tuples recorded by curl_fn.
    How: Split on slash after stripping a trailing slash and query string.
    """
    tails = []
    for _method, url, *_rest in calls:
        tail = url.rstrip("/").split("/")[-1].split("?")[0]
        tails.append(tail)
    return tails


def test_dry_run_without_mr():
    assert is_mr_context({}) is False
    assert is_dry_run({}) is True
    env = {"REVIEW_DRY_RUN": "1", "CI_MERGE_REQUEST_IID": "12"}
    assert is_dry_run(env) is True


def test_missing_token_on_mr_fails_and_does_not_approve():
    calls = []

    def curl_fn(*args, **kwargs):
        calls.append((args, kwargs))
        return 200, {}

    assert run_review(_mr_env(token=""), curl_fn=curl_fn) == 1
    assert calls == []


def test_setup_steps_name_the_token():
    text = setup_steps()
    assert "GITLAB_REVIEWER_TOKEN" in text
    assert "Project Access Token" in text
    assert "api" in text
    assert "masked" in text


def test_pip_audit_does_not_block():
    ok, lines = evaluate_jobs(_jobs(pip="failed"))
    assert ok is True
    assert any("does not block" in line for line in lines)


def test_node_audit_blocks():
    ok, lines = evaluate_jobs(_jobs(node="failed"))
    assert ok is False
    assert any("security:node" in line and "hold" in line for line in lines)


def test_missing_blocking_job_holds():
    ok, lines = evaluate_jobs([{"name": "backend", "status": "success"}])
    assert ok is False
    assert any("frontend: missing" in line for line in lines)
    blob = "\n".join(lines)
    for name in BLOCKING_JOBS:
        assert name in blob


def test_caret_pin_is_a_finding():
    diff = _hunk("frontend/package.json", '    "react": "^18.3.1",')
    findings = scan_diff(parse_diff(diff))
    assert any("not an exact pin" in item for item in findings)


def test_unapproved_package_is_a_finding():
    diff = _hunk("backend/requirements.txt", "requests==2.0.0")
    findings = scan_diff(parse_diff(diff))
    assert any("requests is not on the approved list" in item for item in findings)


def test_title_attr_is_a_finding():
    diff = _hunk("frontend/src/Docs.jsx", '<a title="hint">docs</a>')
    findings = scan_diff(parse_diff(diff))
    assert any("title=" in item for item in findings)


def test_folder_frame_is_a_finding():
    diff = _hunk(
        "frontend/src/index.css",
        "  width: min(1180px, 100%);",
        "  clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%);",
    )
    findings = scan_diff(parse_diff(diff))
    assert any("1180" in item or "clip-path" in item for item in findings)


def test_new_function_without_comment_is_a_finding():
    diff = _hunk("backend/app.py", "def brand_new_helper():", "    return 1")
    findings = scan_diff(parse_diff(diff))
    assert any("five-part" in item for item in findings)


def test_new_function_with_comment_passes():
    diff = _hunk(
        "backend/app.py",
        "def brand_new_helper():",
        '    """',
        "    What: Helper used only in this unit test.",
        "    Why: Prove a documented new function is not a finding.",
        "    Who: The reviewer bot scan_diff path.",
        "    Where: A synthetic backend module hunk.",
        "    How: Return a constant after the five-part docstring.",
        '    """',
        "    return 1",
    )
    findings = scan_diff(parse_diff(diff))
    assert not any("five-part" in item for item in findings)


def test_decide_approve_hold_unapprove():
    assert decide(False, "", False, [], False) == "dry-run"
    assert decide(True, "", True, [], False) == "missing-token"
    assert decide(True, "tok", True, [], False) == "approve"
    assert decide(True, "tok", False, [], True) == "unapprove"
    assert decide(True, "tok", False, ["x"], False) == "hold"
    assert decide(True, "tok", True, ["x"], False) == "hold"


def test_parse_diff_paths():
    diff = _hunk("foo.py", "print(1)")
    files = parse_diff(diff)
    assert files[0]["path"] == "foo.py"


def test_build_note_has_sections():
    note = build_note("HOLD", ["backend: success"], ["pin miss"], "Holding.")
    assert "**Verdict:** HOLD" in note
    assert "### Pipeline" in note
    assert "### Findings" in note
    assert "pin miss" in note


def test_approve_path_posts_note_and_approve():
    calls = []

    def curl_fn(method, url, token, body=None):
        calls.append((method, url, token, body))
        if "changes" in url:
            return 200, {"changes": []}
        if "jobs" in url:
            return 200, _jobs(pip="failed")
        if "approvals" in url:
            return 200, {"approved": False}
        if url.rstrip("/").endswith("/notes"):
            return 201, {}
        if url.rstrip("/").endswith("/approve"):
            return 201, {}
        return 404, {}

    assert run_review(_mr_env(), curl_fn=curl_fn) == 0
    tails = _tails(calls)
    assert "approve" in tails
    assert "unapprove" not in tails
    assert any(method == "POST" and "notes" in url for method, url, *_ in calls)


def test_unapprove_on_later_red_push():
    calls = []

    def curl_fn(method, url, token, body=None):
        calls.append((method, url, token, body))
        if "changes" in url:
            return 200, {"changes": []}
        if "jobs" in url:
            return 200, _jobs(backend="failed")
        if "approvals" in url:
            return 200, {"approved": True}
        if url.rstrip("/").endswith("/notes"):
            return 201, {}
        if url.rstrip("/").endswith("/unapprove"):
            return 201, {}
        return 404, {}

    assert run_review(_mr_env(), curl_fn=curl_fn) == 1
    tails = _tails(calls)
    assert "unapprove" in tails
    assert "approve" not in tails


def test_dry_run_exits_zero(capsys):
    assert run_review({"REVIEW_DRY_RUN": "1"}) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "Approve" not in out or "Would" in out
