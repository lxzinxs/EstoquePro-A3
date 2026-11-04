"""Smoke test isolado de imagem/Gunicorn/PostgreSQL. Não monta bancos do usuário."""

import argparse
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from runtime import DockerUnavailable, docker_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="estoquepro:review")
    args = parser.parse_args()
    try:
        docker, env = docker_runtime()
    except DockerUnavailable as exc:
        raise SystemExit(str(exc))
    suffix = uuid.uuid4().hex[:12]
    network = "estoquepro-review-" + suffix
    pgname = network + "-db"
    appname = network + "-app"

    def run(*arguments, **kwargs):
        return subprocess.run([*docker, *arguments], env=env, check=True, **kwargs)

    with tempfile.TemporaryDirectory(prefix="estoquepro-smoke-") as temporary:
        password = secrets.token_urlsafe(32)
        pgfile = Path(temporary) / "pg.env"
        appfile = Path(temporary) / "app.env"
        pgfile.write_text(
            "POSTGRES_DB=review\nPOSTGRES_USER=review\nPOSTGRES_PASSWORD=" + password + "\n"
        )
        pgfile.chmod(0o600)
        appfile.write_text(
            "PGDATABASE=review\nPGUSER=review\nPGPASSWORD="
            + password
            + "\nPGHOST="
            + pgname
            + "\nPGPORT=5432\nDJANGO_DEBUG=0\nDJANGO_SECRET_KEY="
            + secrets.token_urlsafe(64)
            + "\nDJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\nDJANGO_TRUST_PROXY_HEADERS=1\n"
        )
        appfile.chmod(0o600)
        run("network", "create", network, stdout=subprocess.DEVNULL)
        try:
            run(
                "run",
                "--rm",
                "-d",
                "--name",
                pgname,
                "--network",
                network,
                "--env-file",
                str(pgfile),
                "postgres:17-bookworm",
                stdout=subprocess.DEVNULL,
            )
            for _ in range(60):
                ready = subprocess.run(
                    [*docker, "exec", pgname, "pg_isready", "-U", "review", "-d", "review"],
                    env=env,
                    capture_output=True,
                    check=False,
                )
                if ready.returncode == 0:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("PostgreSQL temporário não iniciou.")
            run(
                "run",
                "--rm",
                "-d",
                "--name",
                appname,
                "--network",
                network,
                "--env-file",
                str(appfile),
                args.image,
                stdout=subprocess.DEVNULL,
            )
            run(
                "exec",
                appname,
                "python",
                "manage.py",
                "migrate",
                "--noinput",
                stdout=subprocess.DEVNULL,
            )
            run(
                "exec",
                appname,
                "python",
                "manage.py",
                "collectstatic",
                "--noinput",
                stdout=subprocess.DEVNULL,
            )
            run(
                "exec",
                appname,
                "python",
                "manage.py",
                "runworker",
                "--once",
                stdout=subprocess.DEVNULL,
            )
            code = """import http.client,os
from pathlib import Path
assert os.getuid()==10001
assert not Path('/app/data/django-local.env').exists()
assert not Path('/app/data/estoquepro.sqlite3').exists()
assert not Path('/app/data/backups').exists()
assert Path('/app/data/static/django.css').is_file()
assert Path('/app/data/static/django.js').is_file()
c=http.client.HTTPConnection('127.0.0.1',8000,timeout=10)
c.request('GET','/accounts/login/',headers={'X-Forwarded-Proto':'https'})
r=c.getresponse();body=r.read();assert r.status==200
assert b'Entrar no sistema' in body and b'Cadastro' in body
assert r.getheader('X-Content-Type-Options')=='nosniff'
assert 'Secure' in r.getheader('Set-Cookie')
c.request('GET','/accounts/login/')
r=c.getresponse();r.read();assert r.status==301 and r.getheader('Location').startswith('https://')
c.close()
print('Gunicorn HTTP, cookies seguros, redirecionamento HTTPS, estáticos coletados, UID sem root e ausência de dados pessoais: OK')
"""
            run("exec", appname, "python", "-c", code)
            print("Migrações, PostgreSQL temporário, collectstatic e worker em container: OK")
        finally:
            for name in [appname, pgname]:
                subprocess.run(
                    [*docker, "rm", "-f", "-v", name],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            subprocess.run(
                [*docker, "network", "rm", network],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    main()
