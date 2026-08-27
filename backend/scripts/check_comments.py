"""Fail the build when first-party functions lack a quality five-part comment."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comment_lib import run_check

if __name__ == "__main__":
    failures, paths = run_check(sys.argv[1:])
    if failures:
        print("comment check failed:")
        for item in failures:
            print(item)
        sys.exit(1)
    print("comment check passed (%d file(s))" % len(paths))
