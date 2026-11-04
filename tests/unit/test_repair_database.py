import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.repair_database import repair_password, scram_verifier


class RepairDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.values = dict(
            PGHOST="127.0.0.1", PGPORT="55432", PGUSER='local"role', PGPASSWORD="private-password"
        )

    @patch("scripts.repair_database.subprocess.run")
    def test_refuses_nonlocal_database(self, run):
        self.values["PGHOST"] = "example.com"
        with self.assertRaises(ValueError):
            repair_password(self.values, ["docker"], {})
        run.assert_not_called()

    @patch("scripts.repair_database.subprocess.run")
    def test_refuses_unexpected_port_binding(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="0.0.0.0:55432")
        with self.assertRaises(ValueError):
            repair_password(self.values, ["docker"], {})
        self.assertEqual(run.call_count, 1)

    @patch("scripts.repair_database.subprocess.run")
    def test_updates_only_role_using_verifier_on_stdin(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="127.0.0.1:55432\n"),
            SimpleNamespace(returncode=0),
        ]
        repair_password(self.values, ["docker"], {})
        args, kwargs = run.call_args
        self.assertNotIn("private-password", str(args) + str(kwargs))
        self.assertIn('ALTER ROLE "local""role" PASSWORD', kwargs["input"])
        self.assertIn("SCRAM-SHA-256$4096:", kwargs["input"])
        self.assertTrue(kwargs["capture_output"])

    @patch("scripts.repair_database.subprocess.run")
    def test_server_errors_are_not_echoed(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="127.0.0.1:55432\n"),
            SimpleNamespace(returncode=1, stderr="private-password"),
        ]
        with self.assertRaises(ValueError) as exc:
            repair_password(self.values, ["docker"], {})
        self.assertNotIn("private-password", str(exc.exception))

    def test_verifier_is_salted_and_unicode_is_rejected(self):
        self.assertNotEqual(scram_verifier("same-password"), scram_verifier("same-password"))
        with self.assertRaises(UnicodeEncodeError):
            scram_verifier("senha-com-acentuação")
