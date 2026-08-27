"""Fail the build when first-party functions lack a five-part comment.

Inventories functions plus pipeline YAML jobs, dependabot updates,
Makefile targets, and pipeline.sh case arms with the same quality bar.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PARTS = ("WHAT", "WHY", "WHO", "WHERE", "HOW")
LABEL_RE = re.compile(
    r"^\s*(?:#\s*)?(?:\*\s*)?(WHAT|WHY|WHO|WHERE|HOW)\s*:\s*(.*)$",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"\b(TODO|TBD|FIXME|XXX|placeholder|self-explanatory|n/?a)\b",
    re.IGNORECASE,
)
JS_FUNC_DECL_RE = re.compile(
    r"(?:^|[\s=;])(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\("
)
JS_CONST_ARROW_RE = re.compile(
    r"^(?P<indent>\s*)(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s+)?(?:\([^;]*?\)|[A-Za-z_$][\w$]*)\s*=>"
)
JS_CONST_START_RE = re.compile(
    r"^(?P<indent>\s*)(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s+)?\("
)
JS_METHOD_RE = re.compile(
    r"^(?P<indent>\s*)(?:async\s+)?(?P<name>[A-Za-z_$][\w$]*)\s*\([^;]*\)\s*\{"
)
JS_SKIP_METHOD_NAMES = {
    "if", "for", "while", "switch", "catch", "else", "do", "try",
    "function", "return", "with", "class", "const", "let", "var",
    "export", "import", "from", "async", "await", "new", "typeof",
    "instanceof", "in", "of", "this", "super", "case", "default",
    "throw", "finally", "interface", "type", "enum",
}

def repo_rel(path: Path) -> str:
    """
    What: Format a filesystem path relative to the portal repo root.
    Why: Failure lines must be stable file:line:name:reason, not absolute.
    Who: report printers in main().
    Where: backend/scripts/check_comments.py output.
    How: Path.relative_to(ROOT) with forward slashes so CI and local match.
    """
    return path.resolve().relative_to(ROOT).as_posix()


def normalize(text: str) -> str:
    """
    What: Collapse a comment or source snippet for equality checks.
    Why: HOW-vs-body and WHAT-vs-WHY compares should ignore punctuation noise.
    Who: quality_reasons and how_copies_body.
    Where: Checker comparisons only.
    How: Lowercase, squeeze whitespace, strip trailing .;: .
    """
    squeezed = re.sub(r"\s+", " ", text or "").strip()
    return squeezed.lower().strip(".;:")


def parse_five_parts(comment: str) -> dict[str, str]:
    """
    What: Pull WHAT/WHY/WHO/WHERE/HOW values out of a house-style comment.
    Why: Both Python docstrings and JS blocks use the same five labels.
    Who: check_python_file and check_js_file after they locate a comment.
    Where: Immediately above (JS) or under (Python) a function.
    How: Scan lines for Label: text; keep reading unlabeled continuations.
    """
    parts: dict[str, str] = {}
    current: str | None = None
    for raw in (comment or "").splitlines():
        match = LABEL_RE.match(raw.rstrip())
        if match:
            current = match.group(1).upper()
            parts[current] = match.group(2).strip()
            continue
        if current is None:
            continue
        extra = raw.strip()
        if extra.startswith("*"):
            extra = extra[1:].strip()
        if extra:
            parts[current] = (parts[current] + " " + extra).strip()
    return parts


def comment_is_placeholder(comment: str, parts: dict[str, str]) -> str | None:
    """
    What: Detect reserved low-quality stand-in wording in a five-part comment.
    Why: Those phrases are the quality bar's explicit fail tokens.
    Who: quality_reasons.
    Where: Combined comment text plus each part value.
    How: Regex for the reserved fail-token list in the house style.
    """
    blob = comment + " " + " ".join(parts.values())
    if PLACEHOLDER_RE.search(blob):
        return "placeholder/TODO/self-explanatory"
    return None


def first_python_body(source: str, node: ast.AST) -> str:
    """
    What: First executable statement of a Python function, as source text.
    Why: HOW must not copy the next source line.
    Who: quality_reasons for Python defs.
    Where: Function body after the five-part docstring.
    How: Skip the leading docstring Expr; ast.get_source_segment on the next stmt.
    """
    body = list(getattr(node, "body", []) or [])
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], "value", None), ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        return ""
    snippet = ast.get_source_segment(source, body[0]) or ""
    return snippet.strip()


def first_js_body(lines: list[str], start_idx: int) -> str:
    """
    What: First meaningful JavaScript line of a function body.
    Why: HOW must not restate the next source line.
    Who: quality_reasons for JS/JSX functions.
    Where: Lines after the signature's { or =>.
    How: Walk forward, skip blanks/comments/braces, return the first code line.
    """
    i = start_idx
    seen_sig = False
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not seen_sig:
            if "=>" in raw or "{" in raw:
                seen_sig = True
                after = ""
                if "=>" in raw:
                    after = raw.split("=>", 1)[1].strip()
                elif "{" in raw:
                    after = raw.split("{", 1)[1].strip()
                after = after.strip("{").strip()
                if after and not after.startswith("//") and after != "}":
                    return after.rstrip(";").strip()
            i += 1
            continue
        if not stripped or stripped in {"{", "}", "};"}:
            i += 1
            continue
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            i += 1
            continue
        return stripped.rstrip(";").strip()
    return ""


def quality_reasons(comment, parts, body):
    """
    What: List why a five-part comment fails the quality bar.
    Why: Labels alone are not enough; HOW must not copy the next source line.
    Who: check_python_file and check_js_file.
    Where: backend/scripts during make check.
    How: Missing or short parts, placeholders, WHAT equals WHY, HOW copies body.
    """
    reasons = []
    missing = [name for name in PARTS if not (parts.get(name) or "").strip()]
    if missing:
        return ["missing " + ",".join(missing)]
    for name in PARTS:
        if len(parts[name].strip()) < 8:
            reasons.append(name + " too short")
    held = comment_is_placeholder(comment, parts)
    if held:
        reasons.append(held)
    if normalize(parts.get("WHAT", "")) == normalize(parts.get("WHY", "")):
        reasons.append("WHAT equals WHY")
    body_n = normalize(body)
    how_n = normalize(parts.get("HOW", ""))
    if body_n and how_n and (how_n == body_n or (len(body_n) > 20 and body_n in how_n)):
        reasons.append("HOW copies body")
    return reasons

def python_docstring(node):
    """
    What: Return the leading docstring of a Python function, or empty.
    Why: House comments live in the def docstring, not a block above.
    Who: check_python_file.
    Where: ast FunctionDef / AsyncFunctionDef.
    How: ast.get_docstring clean=False; None becomes an empty string.
    """
    return ast.get_docstring(node, clean=False) or ""


def check_python_file(path, source):
    """
    What: Inventory Python functions and fail those with a weak five-part comment.
    Why: make check must exit 1 on missing What/Why/Who/Where/How.
    Who: main for each backend py file in the delta.
    Where: backend/*.py and backend/scripts/*.py.
    How: ast.walk FunctionDef; report file:line:name:reason.
    """
    failures = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{repo_rel(path)}:{exc.lineno or 1}:<parse>:syntax error"]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        comment = python_docstring(node)
        parts = parse_five_parts(comment)
        body = first_python_body(source, node)
        reasons = quality_reasons(comment, parts, body)
        if reasons:
            line = getattr(node, "lineno", 1)
            failures.append(f"{repo_rel(path)}:{line}:{node.name}:{'; '.join(reasons)}")
    return failures

def preceding_js_comment(lines, idx):
    """
    What: Collect the block comment immediately above a JS function.
    Why: Frontend five-part comments sit above the signature, not inside.
    Who: check_js_file.
    Where: frontend/src lines before the def.
    How: Walk up through blanks; take a closed block comment or slash comments.
    """
    i = idx - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0:
        return ""
    if lines[i].rstrip().endswith("*" + "/"):
        end = i
        while i >= 0 and not lines[i].lstrip().startswith("/*"):
            i -= 1
        if i < 0:
            return ""
        return "\n".join(lines[i:end + 1])
    if lines[i].lstrip().startswith("//"):
        end = i
        while i >= 0 and lines[i].lstrip().startswith("//"):
            i -= 1
        return "\n".join(lines[i + 1:end + 1])
    return ""


def js_candidates(lines):
    """
    What: Find JS/JSX function names and the line index they start on.
    Why: The checker must cover decls, exported arrows, and object methods.
    Who: check_js_file.
    Where: frontend/src lines.
    How: Regex for function, const arrow, and method brace; skip keywords.
    """
    found = []
    for idx, line in enumerate(lines):
        match = JS_FUNC_DECL_RE.search(line)
        if match:
            found.append((idx, match.group("name")))
            continue
        match = JS_CONST_ARROW_RE.match(line)
        if match:
            found.append((idx, match.group("name")))
            continue
        match = JS_CONST_START_RE.match(line)
        if match and "=>" in "".join(lines[idx:idx + 4]):
            found.append((idx, match.group("name")))
            continue
        match = JS_METHOD_RE.match(line)
        if match and match.group("name") not in JS_SKIP_METHOD_NAMES:
            found.append((idx, match.group("name")))
    return found


def check_js_file(path, source):
    """
    What: Inventory JS/JSX functions and fail weak five-part comments.
    Why: SPA helpers and pages share the same house comment rule.
    Who: main for frontend/src files in the delta.
    Where: js and jsx under frontend/src.
    How: js_candidates plus preceding_js_comment plus quality_reasons.
    """
    lines = source.splitlines()
    failures = []
    for idx, name in js_candidates(lines):
        comment = preceding_js_comment(lines, idx)
        parts = parse_five_parts(comment)
        body = first_js_body(lines, idx)
        reasons = quality_reasons(comment, parts, body)
        if reasons:
            failures.append(f"{repo_rel(path)}:{idx + 1}:{name}:{'; '.join(reasons)}")
    return failures

def _is_first_party(path):
    """
    What: True when a path is a first-party Python or JS source we grade.
    Why: Mock HTML, dist, and node_modules must not fail the comment check.
    Who: git_delta_paths and all_first_party.
    Where: backend py files and frontend/src js/jsx.
    How: Suffix plus directory prefix; skip scratch _part files, venv, and test trees.
    """
    rel = repo_rel(path)
    if rel in CONFIG_RELS:
        return True
    if "/_part" in rel:
        return False
    if "/tests/" in rel or rel.endswith(".test.js") or rel.endswith(".test.jsx"):
        return False
    if rel.startswith("backend/") and path.suffix == ".py":
        if "/doxygen-mock/" in rel or "/.venv/" in rel or "/mailbox/" in rel:
            return False
        return True
    if rel.startswith("frontend/src/") and path.suffix in {".js", ".jsx"}:
        return True
    return False


def git_delta_paths(base=None):
    """
    What: List first-party files changed in the working tree or last commit.
    Why: Comments-grade is the commit delta, not a 75-function repo walk.
    Who: main when --diff is set (make check default).
    Where: git diff --name-only against BASE, or HEAD~1 when the tree is clean.
    How: porcelain empty means diff HEAD~1..HEAD; else diff plus untracked vs HEAD.
    """

    def run(args):
        """
        What: Run a git command at the portal repo root and return stdout.
        Why: Path collection must use this checkout, not the caller cwd.
        Who: git_delta_paths.
        Where: ROOT of f18-okta-portal.
        How: subprocess.check_output text=True cwd=ROOT.
        """
        return subprocess.check_output(args, cwd=ROOT, text=True)

    porcelain = run(["git", "status", "--porcelain"]).strip()
    if base:
        names = run(["git", "diff", "--name-only", base]).splitlines()
        names += run(["git", "ls-files", "--others", "--exclude-standard"]).splitlines()
    elif porcelain:
        names = run(["git", "diff", "--name-only", "HEAD"]).splitlines()
        names += run(["git", "diff", "--name-only", "--cached"]).splitlines()
        names += run(["git", "ls-files", "--others", "--exclude-standard"]).splitlines()
    else:
        names = run(["git", "diff", "--name-only", "HEAD~1", "HEAD"]).splitlines()
    paths = []
    seen = set()
    for name in names:
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        path = ROOT / name
        if path.is_file() and _is_first_party(path):
            paths.append(path)
    return paths

def all_first_party():
    """
    What: Every first-party source file (opt-in --all, not make check).
    Why: Operators can sweep the tree without changing the default delta rule.
    Who: main when --all is passed.
    Where: backend and frontend/src.
    How: glob/rglob, then _is_first_party.
    """
    backend = ROOT / "backend"
    frontend_src = ROOT / "frontend" / "src"
    paths = list(backend.glob("*.py"))
    paths += list((backend / "scripts").glob("*.py"))
    paths += list(frontend_src.rglob("*.js"))
    paths += list(frontend_src.rglob("*.jsx"))
    paths += [ROOT / rel for rel in CONFIG_RELS]
    return [p for p in paths if p.is_file() and _is_first_party(p)]

def check_path(path):
    """
    What: Dispatch a file to the Python or JS comment checker.
    Why: One entry so main can print a single failure list.
    Who: main loop.
    Where: Each first-party path.
    How: Suffix py uses check_python_file; js/jsx uses check_js_file.
    """
    source = path.read_text(encoding="utf-8")
    rel = repo_rel(path)
    if rel == "scripts/pipeline.sh":
        return check_pipeline_sh(path, source)
    if path.name == "Makefile":
        return check_makefile(path, source)
    if rel == ".github/dependabot.yml":
        return check_dependabot(path, source)
    if path.suffix in {".yml", ".yaml"} and rel in CONFIG_RELS:
        return check_yaml_jobs(path, source)
    if path.suffix == ".py":
        return check_python_file(path, source)
    return check_js_file(path, source)

def run_check(args):
    """
    What: Run the five-part comment quality gate over chosen paths.
    Why: make check must fail when a delta function is undocumented.
    Who: check_comments.py entry.
    Where: backend/scripts/comment_lib.py.
    How: --all sweeps the tree; otherwise git_delta_paths; return failure lines.
    """
    use_all = "--all" in args
    base = None
    if "--base" in args:
        idx = args.index("--base")
        if idx + 1 < len(args):
            base = args[idx + 1]
    if use_all:
        paths = all_first_party()
    else:
        paths = git_delta_paths(base)
    failures = []
    for path in sorted(paths):
        failures.extend(check_path(path))
    return failures, paths

CONFIG_RELS = (
    ".github/workflows/ci.yml",
    ".github/workflows/security.yml",
    ".github/workflows/agents.yml",
    ".github/dependabot.yml",
    ".gitlab-ci.yml",
    "Makefile",
    "scripts/pipeline.sh",
)

YAML_TOP_SKIP = frozenset(
    {
        "name",
        "on",
        "concurrency",
        "permissions",
        "env",
        "defaults",
        "run-name",
        "workflow",
        "stages",
        "variables",
        "default",
        "include",
        "image",
        "cache",
        "before_script",
        "after_script",
    }
)


def preceding_hash_comment(lines, idx):
    """
    What: Collect the # comment block immediately above a config item.
    Why: YAML jobs, make targets, and shell case arms keep house comments above the name.
    Who: The config-block checkers below.
    Where: Lines just before a job, update, target, or case arm.
    How: Skip blanks, then take a run of hash comments. Empty if the neighbor is code.
    """
    i = idx - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0 or not lines[i].lstrip().startswith("#"):
        return ""
    end = i
    while i >= 0 and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        i -= 1
    chunk = [line for line in lines[i + 1 : end + 1] if line.lstrip().startswith("#")]
    return "\n".join(chunk)


def next_indented_body(lines, idx):
    """
    What: First non-comment line that belongs to a YAML block.
    Why: HOW must not copy the next real key or script line.
    Who: check_yaml_jobs and check_dependabot.
    Where: Lines after a job or package-ecosystem key.
    How: Walk forward and return the first non-empty, non-hash line.
    """
    i = idx + 1
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        return stripped
    return ""


def report_config(path, line, name, comment, body):
    """
    What: Build failure lines for one config block using the function quality bar.
    Why: Jobs and targets must fail for the same reasons a function fails.
    Who: Each config checker after it finds a name and its comment.
    Where: file:line:name:reason, same shape as Python and JS reports.
    How: parse_five_parts plus quality_reasons; empty list when the block is clean.
    """
    parts = parse_five_parts(comment)
    reasons = quality_reasons(comment, parts, body)
    if not reasons:
        return []
    return [f"{repo_rel(path)}:{line}:{name}:{'; '.join(reasons)}"]


def check_yaml_jobs(path, source):
    """
    What: Inventory GitHub and GitLab pipeline jobs and grade their comments.
    Why: Function --all used to skip YAML, so a job could ship with no layman comment.
    Who: check_path for workflow and .gitlab-ci.yml files.
    Where: A jobs: map on GitHub, or top-level job keys on GitLab.
    How: Find job names, take the hash block above each, score with quality_reasons.
    """
    lines = source.splitlines()
    failures = []
    in_jobs = False
    github_style = any(re.match(r"^jobs:\s*$", line) for line in lines)
    for idx, line in enumerate(lines):
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if github_style:
            if in_jobs and line and not line.startswith(" ") and not line.startswith("#"):
                in_jobs = False
            match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
            if not (in_jobs and match):
                continue
            name = match.group(1)
        else:
            match = re.match(r"^([A-Za-z0-9_.:-]+):\s*$", line)
            if not match or match.group(1) in YAML_TOP_SKIP:
                continue
            name = match.group(1)
        comment = preceding_hash_comment(lines, idx)
        body = next_indented_body(lines, idx)
        failures.extend(report_config(path, idx + 1, name, comment, body))
    return failures


def check_dependabot(path, source):
    """
    What: Inventory each Dependabot ecosystem update and grade its comment.
    Why: A weekly update block without layman comments is a config-block miss.
    Who: check_path for .github/dependabot.yml.
    Where: Each package-ecosystem list item.
    How: Name the block from the ecosystem value; score the hash block above it.
    """
    lines = source.splitlines()
    failures = []
    for idx, line in enumerate(lines):
        match = re.match(r"^\s*-\s+package-ecosystem:\s*(\S+)\s*$", line)
        if not match:
            continue
        name = match.group(1).strip().strip("\"'")
        comment = preceding_hash_comment(lines, idx)
        body = next_indented_body(lines, idx)
        failures.extend(report_config(path, idx + 1, name, comment, body))
    return failures


def check_makefile(path, source):
    """
    What: Inventory Makefile targets and grade the comment above each one.
    Why: make ci names must stay documented the same way functions are.
    Who: check_path for the repo-root Makefile.
    Where: Target lines that are not dot-specials like .PHONY.
    How: Regex for name: at column 0; body is the first tab recipe or prereq list.
    """
    lines = source.splitlines()
    failures = []
    for idx, line in enumerate(lines):
        if line.startswith("\t") or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_./?*%@+-]+):(\s.*)?$", line)
        if not match:
            continue
        name = match.group(1)
        if name.startswith("."):
            continue
        rest = (match.group(2) or "").strip()
        body = rest
        if not body:
            body = next_indented_body(lines, idx)
        comment = preceding_hash_comment(lines, idx)
        failures.extend(report_config(path, idx + 1, name, comment, body))
    return failures


def check_pipeline_sh(path, source):
    """
    What: Inventory pipeline.sh case arms and grade the comment above each one.
    Why: A WHAT-only arm used to pass; the function bar requires all five parts.
    Who: check_path for scripts/pipeline.sh.
    Where: The case \u0022$slice\u0022 in arms, including the fallback star arm.
    How: Lines that look like name); body is the command after the paren.
    """
    lines = source.splitlines()
    failures = []
    in_case = False
    for idx, line in enumerate(lines):
        if re.search(r"\bcase\b.*\bin\b", line):
            in_case = True
            continue
        if in_case and re.match(r"^esac\b", line.strip()):
            break
        if not in_case:
            continue
        match = re.match(r"^(\s*)([^)#]+)\s*\)(.*)$", line)
        if not match:
            continue
        name = match.group(2).strip()
        if name == "*":
            name = "star"
        body = match.group(3).strip().rstrip(";").strip()
        if not body:
            body = next_indented_body(lines, idx)
        comment = preceding_hash_comment(lines, idx)
        failures.extend(report_config(path, idx + 1, name, comment, body))
    return failures
