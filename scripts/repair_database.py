"""Explicit recovery for the dedicated local development PostgreSQL container."""

import base64
import hashlib
import hmac
import secrets
import subprocess


def scram_verifier(password):
    # Local setup generates an ASCII password. Refuse custom Unicode passwords rather
    # than implementing PostgreSQL's SASLprep normalization incorrectly.
    password.encode("ascii")
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
    client = hmac.digest(salted, b"Client Key", "sha256")
    stored = hashlib.sha256(client).digest()
    server = hmac.digest(salted, b"Server Key", "sha256")

    def encode(value):
        return base64.b64encode(value).decode("ascii")

    return f"SCRAM-SHA-256$4096:{encode(salt)}${encode(stored)}:{encode(server)}"


def repair_password(values, docker, env):
    if values.get("PGHOST") != "127.0.0.1" or values.get("PGPORT") != "55432":
        raise ValueError("Recuperação limitada ao banco local em 127.0.0.1:55432.")
    password = values.get("PGPASSWORD", "")
    if not password:
        raise ValueError("PGPASSWORD ausente. Nenhuma alteração realizada.")
    try:
        verifier = scram_verifier(password)
    except UnicodeEncodeError:
        raise ValueError("Recuperação automática exige a senha ASCII gerada pelo setup.") from None
    port = subprocess.run(
        docker + ["port", "nerythstock-postgres", "5432/tcp"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if port.returncode or port.stdout.strip() != "127.0.0.1:55432":
        raise ValueError(
            "O container não publica a porta local esperada. Nenhuma alteração realizada."
        )
    role = values["PGUSER"].replace('"', '""')
    # Only a salted verifier crosses stdin. No password in argv, SQL, or output.
    statement = f"ALTER ROLE \"{role}\" PASSWORD '{verifier}';\n"
    result = subprocess.run(
        docker
        + [
            "exec",
            "-i",
            "nerythstock-postgres",
            "psql",
            "-X",
            "-w",
            "-h",
            "/var/run/postgresql",
            "-U",
            values["PGUSER"],
            "-d",
            "postgres",
            "--set",
            "ON_ERROR_STOP=1",
        ],
        input=statement,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode:
        raise ValueError(
            "Não foi possível atualizar a senha via conexão interna. Nenhum dado foi apagado. "
            "O usuário configurado precisa existir e permitir a conexão local no container."
        )
