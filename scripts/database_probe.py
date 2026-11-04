"""Connection diagnostics with fixed messages: never print libpq errors or secrets."""

import sys


def diagnose(connect):
    try:
        with connect(connect_timeout=3):
            pass
    except Exception as exc:
        state = getattr(exc, "sqlstate", None)
        detail = str(exc).lower()
        if state in ("28P01", "28000") or "authentication failed" in detail:
            return 1, (
                "PostgreSQL respondeu, mas recusou a autenticação. Confira as credenciais em "
                "data/django-local.env localmente. Um volume existente mantém a senha original; "
                "reescrever postgres-local.env não altera essa senha. Não apague o volume."
            )
        if state == "3D000" or ("database" in detail and "does not exist" in detail):
            return (
                1,
                "PostgreSQL respondeu, mas o banco configurado não existe. Confira PGDATABASE.",
            )
        if "connection refused" in detail:
            return 1, (
                "Conexão PostgreSQL recusada. Confira se o container está ativo e se a porta "
                "publicada corresponde a PGHOST/PGPORT em data/django-local.env. "
                "Execute: docker port nerythstock-postgres"
            )
        if "timeout" in detail or "timed out" in detail:
            return 1, "PostgreSQL não respondeu no prazo. Confira host, porta e serviço do banco."
        return 1, (
            "Falha de conexão PostgreSQL não classificada. Confira a configuração local e "
            "o estado do container. Não compartilhe arquivos .env nem apague o volume."
        )
    return 0, "Conexão PostgreSQL autenticada com sucesso."


def main():
    try:
        import psycopg
    except ImportError:
        print("Driver PostgreSQL ausente. Instale requirements.txt usando o Python da .venv.")
        return 1
    status, message = diagnose(psycopg.connect)
    print(message)
    return status


if __name__ == "__main__":
    sys.exit(main())
