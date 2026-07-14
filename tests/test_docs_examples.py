"""Executable-documentation test: every `arh ...` command in
docs/quickstart.md must actually run.

Commands are extracted from fenced ```bash blocks and executed in order in a
scratch directory that mirrors the repo's samples/ and tests/ (so relative
input paths resolve and output files never dirty the repo). Exit codes 0 and
1 are both acceptable (sample traces intentionally fail); exit code 2 or a
crash means the documentation drifted from the CLI.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUICKSTART = REPO_ROOT / "docs" / "quickstart.md"


def extract_arh_commands(markdown: str) -> list[str]:
    commands = []
    for block in re.findall(r"```bash\n(.*?)```", markdown, flags=re.DOTALL):
        # join line continuations, then keep arh invocations
        joined = block.replace("\\\n", " ")
        for line in joined.splitlines():
            line = line.strip()
            if not line.startswith("arh "):
                continue
            if "<" in line and ">" in line:  # placeholder, not runnable
                continue
            commands.append(line)
    return commands


class TestQuickstartCommands(unittest.TestCase):
    def test_every_arh_command_runs(self):
        markdown = QUICKSTART.read_text(encoding="utf-8")
        commands = extract_arh_commands(markdown)
        self.assertGreaterEqual(
            len(commands), 4, "quickstart lost its runnable examples"
        )
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "samples").symlink_to(REPO_ROOT / "samples")
            (workdir / "tests").symlink_to(REPO_ROOT / "tests")
            for command in commands:
                with self.subTest(command=command):
                    argv = [
                        sys.executable,
                        "-m",
                        "agent_reliability_harness",
                    ] + command.split()[1:]
                    proc = subprocess.run(
                        argv,
                        cwd=workdir,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertIn(
                        proc.returncode,
                        (0, 1),
                        f"'{command}' exited {proc.returncode}\n"
                        f"stdout: {proc.stdout[-2000:]}\n"
                        f"stderr: {proc.stderr[-2000:]}",
                    )


if __name__ == "__main__":
    unittest.main()
