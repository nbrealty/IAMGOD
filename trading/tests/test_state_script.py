"""scripts/state.sh pull (finding #27): an unreachable or unauthorised state remote must stop the session, not be
read as "no saved state yet". Only local file remotes are used (no network)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "state.sh"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                                reason="needs git and bash")


def _env(state_dir: Path, url: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(TRADER_STATE_DIR=str(state_dir), STATE_REPO_URL=url, STATE_BRANCH="trading-state",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@example.com", GIT_TERMINAL_PROMPT="0")
    return env


def _pull(state_dir: Path, url: str):
    return subprocess.run(["bash", str(SCRIPT), "pull"], env=_env(state_dir, url), capture_output=True, text=True,
                          timeout=60)


def _bare(tmp_path: Path, with_branch: bool) -> str:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(bare)], check=True)
    if with_branch:
        work = tmp_path / "seed"
        subprocess.run(["git", "init", "--quiet", str(work)], check=True)
        (work / "rules").mkdir()
        (work / "rules" / "state.json").write_text('{"book": "rules", "last_run_date": "2026-09-25"}')
        env = _env(work, "")
        subprocess.run(["git", "-C", str(work), "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", str(work), "commit", "--quiet", "-m", "seed"], check=True, env=env)
        subprocess.run(["git", "-C", str(work), "push", "--quiet", str(bare), "HEAD:refs/heads/trading-state"],
                       check=True, env=env)
    return bare.as_uri()


def test_missing_branch_starts_empty(tmp_path):
    r = _pull(tmp_path / "state", _bare(tmp_path, with_branch=False))
    assert r.returncode == 0, r.stderr
    assert "does not exist on the remote yet" in r.stdout


def test_existing_branch_is_loaded(tmp_path):
    r = _pull(tmp_path / "state", _bare(tmp_path, with_branch=True))
    assert r.returncode == 0, r.stderr
    assert "state: loaded trading-state" in r.stdout
    assert (tmp_path / "state" / "rules" / "state.json").exists()


def test_unreachable_remote_stops_instead_of_starting_empty(tmp_path):
    missing = (tmp_path / "no-such-remote.git").as_uri()
    r = _pull(tmp_path / "state", missing)
    assert r.returncode != 0
    assert "does not exist on the remote yet" not in r.stdout
    assert "state.sh: could not reach the state remote" in r.stderr


def test_unreachable_remote_stops_an_existing_state_repo_too(tmp_path):
    url = _bare(tmp_path, with_branch=True)
    state = tmp_path / "state"
    assert _pull(state, url).returncode == 0
    shutil.rmtree(tmp_path / "remote.git")  # the remote goes away (network down, token revoked)
    r = _pull(state, url)
    assert r.returncode != 0
    assert "keeping the local state" not in r.stdout
    assert "state.sh: could not reach the state remote" in r.stderr
