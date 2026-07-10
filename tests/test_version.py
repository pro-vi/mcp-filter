"""Package version behavior."""

import subprocess
import sys
from pathlib import Path


def test_source_tree_import_without_distribution_metadata() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import mcp_filter; print(mcp_filter.__version__)"],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(source_root)},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0+unknown"
