import os
import subprocess
import unittest
from pathlib import Path


class LauncherTests(unittest.TestCase):
    def test_windows_launcher_is_ascii_single_line_bootstrap(self):
        project_dir = Path(__file__).resolve().parents[1]
        launcher = project_dir / "启动项目.bat"

        content = launcher.read_bytes()

        self.assertTrue(all(byte < 128 for byte in content))
        self.assertEqual(len(content.splitlines()), 1)
        self.assertIn(b'powershell.exe', content)
        self.assertIn(b'"%~dp0start_project.ps1" %*', content)

    @unittest.skipUnless(os.name == "nt", "Windows launcher integration test")
    def test_windows_launcher_check_mode_parses_without_starting_server(self):
        project_dir = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "call", "启动项目.bat", "-Check"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Launcher check passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
