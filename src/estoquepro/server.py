"""Servidor local de desenvolvimento. Use um proxy TLS para exposição externa."""
import argparse
import csv
import io
import json
import os
import secrets
import sqlite3
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .domain import Inventory, ROOT, ValidationError


class Application(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, inventory):
        super().__init__(address, Handler)
        self.inventory = inventory
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = 'EstoquePro/1.0'

    def log_message(self, format, *args):
        # Não registrar URLs, corpos, cookies ou dados fornecidos pelo usuário.
        pass

    def send(self, status, data, content_type='application/json; charset=utf-8', headers=None):
        body = json.dumps(data, ensure_ascii=False).encode() if 'application/json' in content_type else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def payload(self):
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 16384:
                raise ValueError
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, UnicodeError):
            raise ValidationError('Envie um objeto JSON válido de até 16 KB.') from None

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie['session'].value if 'session' in cookie else ''
        except Exception:
            token = ''
        with self.server.lock:
            now = time.time()
            for key in list(self.server.sessions):
                if self.server.sessions[key]['expires'] <= now:
                    del self.server.sessions[key]
            return token, self.server.sessions.get(token)

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def do_PUT(self):
        self.dispatch('PUT')

    def do_DELETE(self):
        self.dispatch('DELETE')

    def dispatch(self, method):
        try:
            self.route(method)
        except ValidationError as exc:
            self.send(400, {'error': str(exc)})
        except sqlite3.IntegrityError:
            self.send(409, {'error': 'Código ou nome já cadastrado, ou vínculo inválido.'})
        except sqlite3.OperationalError:
            self.send(503, {'error': 'Banco temporariamente indisponível. Tente novamente.'})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.send(500, {'error': 'Falha interna. Consulte o administrador.'})

    def route(self, method):
        url = urlsplit(self.path)
        path = url.path
        db = self.server.inventory
        if method == 'GET' and path in ('/', '/app.js', '/style.css'):
            filename, mime = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}[path]
            return self.send(200, (ROOT / 'src/estoquepro/static' / filename).read_bytes(), mime + '; charset=utf-8')
        if method == 'POST' and path in ('/api/login', '/api/register'):
            # A senha e o token só transitam em JSON/cookie, nunca na URL.
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.send(403, {'error': 'Origem não permitida.'})
            data = self.payload()
            username, password = data.get('username'), data.get('password')
            if not isinstance(username, str) or not isinstance(password, str) or len(username) > 80 or len(password) > 256:
                raise ValidationError('Usuário ou senha inválidos.')
            ip = self.client_address[0]
            with self.server.lock:
                now = time.time()
                self.server.attempts = {k: v for k, v in self.server.attempts.items() if now-v[0] < 60}
                attempts = self.server.attempts.get(ip, (now, 0))
                if attempts[1] >= 10:
                    return self.send(429, {'error': 'Muitas tentativas. Aguarde um minuto.'})
                self.server.attempts[ip] = (attempts[0], attempts[1]+1)
            if path == '/api/register':
                if self.server.server_address[0] not in ('127.0.0.1', '::1'):
                    return self.send(403, {'error': 'Cadastro de usuários disponível apenas na execução local.'})
                user = db.register(data)
            else:
                user = db.authenticate(username.strip().lower(), password)
            if not user:
                return self.send(401, {'error': 'Usuário ou senha incorretos.'})
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            old_token, _ = self.session()
            with self.server.lock:
                self.server.sessions.pop(old_token, None)
                self.server.sessions[token] = {'user': user, 'csrf': csrf, 'expires': time.time()+28800}
            secure = '; Secure' if os.environ.get('ESTOQUEPRO_SECURE_COOKIE') == '1' else ''
            return self.send(201 if path == '/api/register' else 200, {'user': user, 'csrf': csrf}, headers={'Set-Cookie': f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}'})
        token, session = self.session()
        if not session:
            return self.send(401, {'error': 'Entre para continuar.'})
        if method != 'GET' and not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf']):
            return self.send(403, {'error': 'Sessão inválida. Atualize a página.'})
        if path == '/api/session' and method == 'GET':
            return self.send(200, {'user': session['user'], 'csrf': session['csrf']})
        if path == '/api/logout' and method == 'POST':
            with self.server.lock:
                self.server.sessions.pop(token, None)
            return self.send(200, {'ok': True}, headers={'Set-Cookie': 'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
        if path == '/api/dashboard' and method == 'GET':
            return self.send(200, db.dashboard())
        if path in ('/api/categories', '/api/suppliers'):
            table = path.rsplit('/', 1)[1]
            if method == 'GET':
                return self.send(200, db.lookup(table))
            if method == 'POST':
                return self.send(201, {'id': db.add_lookup(table, self.payload())})
        if path == '/api/products':
            if method == 'GET':
                query = parse_qs(url.query)
                return self.send(200, db.products(query.get('q', [''])[0], query.get('category', [''])[0], query.get('low', [''])[0] == '1'))
            if method == 'POST':
                return self.send(201, {'id': db.save_product(self.payload())})
        if path.startswith('/api/products/'):
            try:
                pid = int(path.rsplit('/', 1)[1])
            except ValueError:
                raise ValidationError('Identificador inválido.') from None
            if method == 'PUT':
                return self.send(200, {'id': db.save_product(self.payload(), pid)})
            if method == 'DELETE':
                db.archive(pid)
                return self.send(200, {'ok': True})
        if path == '/api/movements':
            if method == 'GET':
                return self.send(200, db.movements())
            if method == 'POST':
                return self.send(201, {'id': db.move(self.payload(), session['user']['id'])})
        if path == '/api/report.csv' and method == 'GET':
            output = io.StringIO(newline='')
            writer = csv.writer(output, delimiter=';')
            writer.writerow(['Código', 'Produto', 'Categoria', 'Fornecedor', 'Quantidade', 'Mínimo', 'Preço unitário', 'Valor total'])
            def safe(value):
                value = str(value)
                return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
            for p in db.products():
                writer.writerow([safe(p['sku']), safe(p['name']), safe(p['category']), safe(p['supplier'] or ''), p['quantity'], p['minimum'], f"{p['price_cents']/100:.2f}", f"{p['price_cents']*p['quantity']/100:.2f}"])
            return self.send(200, output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', {'Content-Disposition': 'attachment; filename="estoquepro.csv"'})
        self.send(404, {'error': HTTPStatus.NOT_FOUND.phrase})


def main():
    parser = argparse.ArgumentParser(description='EstoquePro — servidor de desenvolvimento local')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--database', default=str(ROOT / 'data/estoquepro.sqlite3'))
    parser.add_argument('--demo', action='store_true', help='Dados fictícios e senha inicial de demonstração')
    parser.add_argument('--reset-demo-admin', action='store_true', help='Redefinir explicitamente admin para admin123 (somente com --demo local)')
    args = parser.parse_args()
    password = os.environ.get('ESTOQUEPRO_ADMIN_PASSWORD')
    inventory = Inventory(args.database)
    existing = False
    if os.path.exists(args.database):
        with inventory.connect() as db:
            if db.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchone():
                existing = bool(db.execute('SELECT id FROM users LIMIT 1').fetchone())
    if not existing and not password and not args.demo:
        parser.error('Defina ESTOQUEPRO_ADMIN_PASSWORD (mínimo 12 caracteres) ou use --demo para demonstração local.')
    if password and not 12 <= len(password) <= 256:
        parser.error('A senha inicial deve ter de 12 a 256 caracteres.')
    if args.host != '127.0.0.1' and args.demo:
        parser.error('O modo demo só permite --host 127.0.0.1.')
    if args.reset_demo_admin and (not args.demo or password):
        parser.error('--reset-demo-admin exige --demo e não pode ser combinado com ESTOQUEPRO_ADMIN_PASSWORD.')
    inventory.initialize(password or 'admin123', args.demo)
    if args.demo and not password and inventory.configure_demo_access(args.reset_demo_admin):
        print('Acesso de demonstração do administrador atualizado.', flush=True)
    print(f'EstoquePro em {args.host}:{args.port} — Ctrl+C para encerrar.', flush=True)
    server = Application((args.host, args.port), inventory)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
