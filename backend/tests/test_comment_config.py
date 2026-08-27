"""Config-block comment coverage."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comment_lib


def test_all_includes_pipeline_config_files():
    rels = {comment_lib.repo_rel(p) for p in comment_lib.all_first_party()}
    for rel in comment_lib.CONFIG_RELS:
        assert rel in rels


def test_current_config_blocks_pass():
    failures, paths = comment_lib.run_check(["--all"])
    config = [p for p in paths if comment_lib.repo_rel(p) in comment_lib.CONFIG_RELS]
    assert len(config) == len(comment_lib.CONFIG_RELS)
    assert failures == []


def test_makefile_target_without_comment_fails():
    src = "foo:" + chr(10) + chr(9) + "echo hi" + chr(10)
    fails = comment_lib.check_makefile(Path("Makefile"), src)
    assert fails
    assert "missing WHAT,WHY,WHO,WHERE,HOW" in fails[0]
