"""CLI invocation tests: the `caesar` console script is the seam."""

import os
import shutil
import subprocess
from importlib.metadata import version


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("caesar")
    assert executable is not None, "`caesar` console script not installed"
    env = {key: value for key, value in os.environ.items() if key != "CAESAR_AGENTS"}
    return subprocess.run(
        [executable, *args], capture_output=True, text=True, timeout=30, env=env
    )


def test_run_with_missing_agent_yml_fails_with_clear_error(tmp_path):
    result = run_cli("run", str(tmp_path))

    assert result.returncode != 0
    assert "agent.yml" in result.stderr


def test_run_with_no_channel_configured_fails_with_clear_error(tmp_path):
    (tmp_path / "agent.yml").write_text("name: Testus\n")

    result = run_cli("run", str(tmp_path))

    assert result.returncode != 0
    assert "No supported channel" in result.stderr


def test_version_flag_reports_package_version():
    result = run_cli("--version")

    assert result.returncode == 0
    assert version("caesar-ai") in result.stdout
