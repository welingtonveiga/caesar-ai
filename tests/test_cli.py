"""CLI invocation tests: the `caesar` console script is the seam."""

import shutil
import subprocess
from importlib.metadata import version


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("caesar")
    assert executable is not None, "`caesar` console script not installed"
    return subprocess.run(
        [executable, *args], capture_output=True, text=True, timeout=30
    )


def test_run_exits_cleanly_with_stub_message():
    result = run_cli("run")

    assert result.returncode == 0
    assert "Caesar" in result.stdout


def test_version_flag_reports_package_version():
    result = run_cli("--version")

    assert result.returncode == 0
    assert version("caesar-ai") in result.stdout
