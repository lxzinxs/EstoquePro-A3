import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.runtime import DockerUnavailable, docker_runtime


class DockerDiagnosisTests(unittest.TestCase):
    @patch("scripts.runtime.shutil.which", return_value=None)
    def test_missing_cli_has_actionable_message(self, which):
        with self.assertRaisesRegex(DockerUnavailable, "Docker não está instalado"):
            docker_runtime()

    @patch(
        "scripts.runtime.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stderr="permission denied"),
    )
    @patch("scripts.runtime.shutil.which", return_value="/usr/bin/docker")
    def test_socket_permission_does_not_suggest_root_project(self, *mocks):
        with self.assertRaisesRegex(DockerUnavailable, "Não execute todo o projeto como root"):
            docker_runtime()

    @patch("scripts.runtime.Path.is_file", return_value=False)
    @patch(
        "scripts.runtime.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stderr=""),
    )
    @patch("scripts.runtime.shutil.which", return_value="/usr/bin/docker")
    def test_native_keeps_desktop_context(self, which, run, is_file):
        with patch.dict("os.environ", {"DOCKER_CONTEXT": "desktop-linux"}):
            command, env = docker_runtime()
        self.assertEqual(command, ["docker"])
        self.assertEqual(env["DOCKER_CONTEXT"], "desktop-linux")
