import unittest
from contextlib import nullcontext
from unittest.mock import Mock

from scripts.database_probe import diagnose


class DatabaseProbeTests(unittest.TestCase):
    def test_success_closes_connection(self):
        connect = Mock(return_value=nullcontext())
        self.assertEqual(diagnose(connect)[0], 0)
        connect.assert_called_once_with(connect_timeout=3)

    def test_failure_messages_never_echo_server_secrets(self):
        for detail, expected in (
            ("password authentication failed: secret-password", "autenticação"),
            ('database "secret-password" does not exist', "não existe"),
            ("connection refused secret-password", "recusada"),
            ("timeout expired secret-password", "prazo"),
            ("unexpected secret-password", "não classificada"),
        ):
            with self.subTest(detail=detail):
                status, message = diagnose(Mock(side_effect=RuntimeError(detail)))
                self.assertEqual(status, 1)
                self.assertIn(expected, message)
                self.assertNotIn("secret-password", message)

    def test_sqlstate_takes_precedence_over_localized_message(self):
        error = RuntimeError("mensagem traduzida")
        error.sqlstate = "28P01"
        self.assertIn("autenticação", diagnose(Mock(side_effect=error))[1])
