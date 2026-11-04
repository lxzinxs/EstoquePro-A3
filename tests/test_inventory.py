import concurrent.futures
import csv
import http.client
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from estoquepro.domain import Inventory, ValidationError, check_password, hash_password, money
from estoquepro.server import Application


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.db = Inventory(self.path)
        self.db.initialize('UmaSenhaForte123')
        self.category = self.db.add_lookup('categories', {'name': 'Categoria teste'})
        self.supplier = self.db.add_lookup('suppliers', {'name': 'Fornecedor teste'})
        self.data = dict(sku='TEST-01', name='Produto teste', category_id=self.category, supplier_id=self.supplier, price='12.90', minimum=2)
        self.pid = self.db.save_product(self.data)
        self.uid = self.db.authenticate('admin', 'UmaSenhaForte123')['id']

    def tearDown(self):
        self.temp.cleanup()

    def move(self, kind, quantity, pid=None):
        return self.db.move(dict(product_id=pid or self.pid, kind=kind, quantity=quantity, note='Teste de movimentação'), self.uid)

    def test_authentication_and_hash(self):
        self.assertIsNone(self.db.authenticate('admin', 'errada'))
        self.assertIsNone(self.db.authenticate("' OR 1=1 --", 'errada'))
        encoded = hash_password('segredo')
        self.assertNotIn('segredo', encoded)
        self.assertTrue(check_password('segredo', encoded))
        self.assertFalse(check_password('outro', encoded))

    def test_register_validation_and_duplicate(self):
        data = dict(username='Novo.Usuario', password='SenhaNova123', confirm_password='SenhaNova123')
        user = self.db.register(data)
        self.assertEqual(user['username'], 'novo.usuario')
        self.assertEqual(self.db.authenticate('novo.usuario', 'SenhaNova123'), user)
        with self.assertRaisesRegex(ValidationError, 'já está cadastrado'):
            self.db.register(data)
        for changes in [dict(username='ab'), dict(username='nome com espaços'), dict(username='<script>'),
                        dict(password='curta', confirm_password='curta'), dict(confirm_password='diferente')]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.db.register({**data, 'username': 'outro.usuario', **changes})

    def test_legacy_demo_migration_preserves_data(self):
        with self.db.connect() as db:
            db.execute("UPDATE users SET password_hash=? WHERE username='admin'", (hash_password('EstoquePro@2026'),))
        before = self.db.products()
        self.assertTrue(self.db.configure_demo_access())
        self.assertIsNotNone(self.db.authenticate('admin', 'admin123'))
        self.assertIsNone(self.db.authenticate('admin', 'EstoquePro@2026'))
        self.assertEqual(self.db.products(), before)
        self.assertFalse(self.db.configure_demo_access())

    def test_demo_preserves_custom_password_until_explicit_reset(self):
        self.assertFalse(self.db.configure_demo_access())
        self.assertIsNotNone(self.db.authenticate('admin', 'UmaSenhaForte123'))
        self.assertTrue(self.db.configure_demo_access(reset=True))
        self.assertIsNotNone(self.db.authenticate('admin', 'admin123'))

    def test_product_create_update_search(self):
        product = self.db.products()[0]
        self.assertEqual(product['quantity'], 0)
        self.assertEqual(product['price_cents'], 1290)
        self.move('entrada', 7)
        self.db.save_product(dict(self.data, name='Nome atualizado', price='9.99'), self.pid)
        found = self.db.products('atualizado', str(self.category))
        self.assertEqual(found[0]['quantity'], 7)
        self.assertEqual(found[0]['price_cents'], 999)
        self.assertEqual(len(self.db.products('TEST-01')), 1)
        self.assertEqual(self.db.products("' OR 1=1 --"), [])

    def test_duplicate_sku_and_lookup(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.save_product(dict(self.data, sku='test-01'))
        for table, name in [('categories', 'categoria teste'), ('suppliers', 'fornecedor teste')]:
            with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                self.db.add_lookup(table, {'name': name})

    def test_product_validation(self):
        for changes in [dict(name=' '), dict(sku=''), dict(category_id=999), dict(supplier_id=999), dict(minimum=-1), dict(minimum=1.5), dict(price='NaN'), dict(price='1.234'), dict(price='-1')]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.db.save_product(dict(self.data, **changes))
        with self.assertRaises(ValidationError):
            self.db.save_product(self.data, 999)

    def test_money_exactness(self):
        self.assertEqual(money('0.29'), 29)
        self.assertEqual(money('123.45'), 12345)

    def test_entry_exit_and_persistence(self):
        self.move('entrada', 10)
        self.move('saida', 3)
        reopened = Inventory(self.path)
        self.assertEqual(reopened.products()[0]['quantity'], 7)
        history = reopened.movements()
        self.assertEqual([m['balance_after'] for m in history], [7, 10])
        self.assertEqual(history[0]['username'], 'admin')
        self.assertEqual(history[0]['note'], 'Teste de movimentação')

    def test_insufficient_balance_rolls_back(self):
        self.move('entrada', 3)
        with self.assertRaisesRegex(ValidationError, 'insuficiente'):
            self.move('saida', 4)
        self.assertEqual(self.db.products()[0]['quantity'], 3)
        self.assertEqual(len(self.db.movements()), 1)

    def test_movement_validation(self):
        for changes in [dict(quantity=0), dict(quantity=-2), dict(quantity=1.2), dict(quantity=True), dict(kind='ajuste'), dict(note=''), dict(product_id=999)]:
            data = dict(product_id=self.pid, kind='entrada', quantity=1, note='Teste')
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.db.move(dict(data, **changes), self.uid)
        self.assertEqual(self.db.movements(), [])

    def test_maximum_balance(self):
        self.move('entrada', 999999999)
        with self.assertRaises(ValidationError):
            self.move('entrada', 1)
        self.assertEqual(self.db.products()[0]['quantity'], 999999999)

    def test_archive_preserves_history_and_reserved_sku(self):
        self.move('entrada', 2)
        with self.assertRaises(ValidationError):
            self.db.archive(self.pid)
        self.move('saida', 2)
        self.db.archive(self.pid)
        self.assertEqual(self.db.products(), [])
        self.assertEqual(len(self.db.movements()), 2)
        with self.assertRaises(ValidationError):
            self.move('entrada', 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.save_product(self.data)

    def test_dashboard_and_low_filter(self):
        self.move('entrada', 2)
        self.assertEqual(self.db.dashboard(), dict(products=1, units=2, value_cents=2580, low=1))
        self.assertEqual(len(self.db.products(low=True)), 1)
        self.move('entrada', 1)
        self.assertEqual(self.db.products(low=True), [])

    def test_concurrent_exits_are_atomic(self):
        self.move('entrada', 5)
        def attempt(_):
            try:
                self.move('saida', 4)
                return True
            except ValidationError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.db.products()[0]['quantity'], 1)
        self.assertEqual(len(self.db.movements()), 2)

    def test_initialization_repeatable_and_demo(self):
        demo_path = Path(self.temp.name) / 'demo.sqlite3'
        demo = Inventory(demo_path)
        demo.initialize('senha-demo', demo=True)
        original = demo.dashboard()
        demo.initialize('outra-senha', demo=True)
        self.assertEqual(demo.dashboard(), original)
        self.assertEqual(original['products'], 4)
        self.assertEqual(original['units'], 94)
        self.assertIsNotNone(demo.authenticate('admin', 'senha-demo'))
        with demo.connect() as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_demo_preserves_partially_configured_catalog(self):
        inventory = Inventory(Path(self.temp.name) / 'partial.sqlite3')
        inventory.initialize('senha-local')
        inventory.add_lookup('suppliers', {'name': 'Fornecedor cadastrado pelo usuário'})
        inventory.initialize('outra-senha', demo=True)
        self.assertEqual(len(inventory.lookup('suppliers')), 1)
        self.assertEqual(inventory.lookup('categories'), [])
        self.assertEqual(inventory.products(), [])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.db = Inventory(Path(cls.temp.name) / 'api.sqlite3')
        cls.db.initialize('SenhaTeste12345', demo=True)
        cls.server = Application(('127.0.0.1', 0), cls.db)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.cookie = ''
        self.csrf = ''
        self.server.attempts.clear()

    def request(self, path, method='GET', data=None, csrf=True, raw=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Cookie': self.cookie, 'Content-Type': 'application/json'}
        if csrf:
            headers['X-CSRF-Token'] = self.csrf
        body = raw if raw is not None else (json.dumps(data) if data is not None else None)
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        content = response.read()
        result = (response.status, dict(response.getheaders()), content)
        connection.close()
        return result

    def login(self):
        status, headers, body = self.request('/api/login', 'POST', dict(username='admin', password='SenhaTeste12345'))
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.csrf = json.loads(body)['csrf']

    def test_static_assets_and_security_headers(self):
        for path in ['/', '/app.js', '/style.css']:
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(self.request('/../../database/schema.sql')[0], 401)

    def test_auth_csrf_logout_and_expiry(self):
        self.assertEqual(self.request('/api/products')[0], 401)
        self.assertEqual(self.request('/api/login', 'POST', dict(username='admin', password='errada'))[0], 401)
        self.login()
        self.assertEqual(self.request('/api/session')[0], 200)
        self.assertEqual(self.request('/api/categories', 'POST', {'name': 'bloqueado'}, csrf=False)[0], 403)
        self.assertEqual(self.request('/api/logout', 'POST', {})[0], 200)
        self.assertEqual(self.request('/api/products')[0], 401)
        self.login()
        self.server.sessions[self.cookie.split('=', 1)[1]]['expires'] = 0
        self.assertEqual(self.request('/api/products')[0], 401)

    def test_complete_api_flow(self):
        self.login()
        status, _, body = self.request('/api/categories', 'POST', {'name': 'Categoria HTTP'})
        self.assertEqual(status, 201)
        category = json.loads(body)['id']
        status, _, body = self.request('/api/suppliers', 'POST', {'name': 'Fornecedor HTTP'})
        self.assertEqual(status, 201)
        supplier = json.loads(body)['id']
        product = dict(name='Produto HTTP', sku='HTTP-01', category_id=category, supplier_id=supplier, price='10.50', minimum=1)
        status, _, body = self.request('/api/products', 'POST', product)
        self.assertEqual(status, 201)
        pid = json.loads(body)['id']
        self.assertEqual(self.request('/api/products', 'POST', product)[0], 409)
        self.assertEqual(self.request(f'/api/products/{pid}', 'PUT', dict(product, name='Atualizado HTTP'))[0], 200)
        move = dict(product_id=pid, kind='entrada', quantity=5, note='Recebimento HTTP')
        self.assertEqual(self.request('/api/movements', 'POST', move)[0], 201)
        self.assertEqual(self.request('/api/movements', 'POST', dict(move, kind='saida', quantity=6))[0], 400)
        status, _, body = self.request('/api/products?q=HTTP-01')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)[0]['quantity'], 5)
        self.assertEqual(self.request(f'/api/products/{pid}', 'DELETE')[0], 400)
        self.assertEqual(self.request('/api/movements', 'POST', dict(move, kind='saida'))[0], 201)
        self.assertEqual(self.request(f'/api/products/{pid}', 'DELETE')[0], 200)
        self.assertEqual(json.loads(self.request('/api/products?q=HTTP-01')[2]), [])
        for path in ['/api/dashboard', '/api/movements', '/api/categories', '/api/suppliers']:
            self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request('/api/unknown')[0], 404)

    def test_public_plan_catalog(self):
        status, _, body = self.request('/api/plans')
        self.assertEqual(status, 200)
        catalog = json.loads(body)
        self.assertFalse(catalog['limits_enforced'])
        self.assertFalse(catalog['billing_enabled'])
        plans = catalog['plans']
        self.assertEqual([p['id'] for p in plans], ['gratis', 'business', 'plus', 'pro'])
        self.assertEqual([p['price_cents'] for p in plans], [0, 4990, 9990, 19990])
        self.assertEqual([(p['accounts'], p['products']) for p in plans], [(1, 50), (2, 100), (5, 300), (None, None)])
        for index, plan in enumerate(plans):
            self.assertEqual(plan['inherits'], plans[index-1]['id'] if index else None)
            self.assertEqual(len({f['name'] for f in plan['features']}), len(plan['features']))
        self.assertEqual(self.request('/plans.js')[0], 200)

    def test_json_errors(self):
        self.login()
        for raw in ['invalid', '[]', '{', '"string"']:
            with self.subTest(raw=raw):
                self.assertEqual(self.request('/api/products', 'POST', raw=raw)[0], 400)

    def test_register_login_and_shared_inventory(self):
        data = dict(username='Conta.HTTP', password='NovaSenhaHTTP123', confirm_password='NovaSenhaHTTP123')
        status, headers, body = self.request('/api/register', 'POST', data)
        self.assertEqual(status, 201)
        user = json.loads(body)['user']
        self.assertEqual(user['username'], 'conta.http')
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.csrf = json.loads(body)['csrf']
        self.assertEqual(self.request('/api/dashboard')[0], 200)
        self.assertEqual(self.request('/api/register', 'POST', data)[0], 400)
        self.assertEqual(self.request('/api/logout', 'POST', {})[0], 200)
        status, _, body = self.request('/api/login', 'POST', dict(username=' CONTA.HTTP ', password='NovaSenhaHTTP123'))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['user'], user)

    def test_register_rejects_invalid_data_and_cross_site(self):
        data = dict(username='valid.user', password='Password123', confirm_password='different')
        self.assertEqual(self.request('/api/register', 'POST', data)[0], 400)
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request('POST', '/api/register', json.dumps(data), {'Content-Type': 'application/json', 'Sec-Fetch-Site': 'cross-site'})
        response = connection.getresponse()
        self.assertEqual(response.status, 403)
        response.read()
        connection.close()

    def test_csv_is_authenticated_and_formula_safe(self):
        self.assertEqual(self.request('/api/report.csv')[0], 401)
        self.login()
        category = self.db.lookup('categories')[0]['id']
        self.db.save_product(dict(name='=HYPERLINK("teste")', sku='CSV-01', category_id=category, price='1', minimum=0))
        status, headers, body = self.request('/api/report.csv')
        self.assertEqual(status, 200)
        self.assertIn('attachment', headers['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(body.decode('utf-8-sig')), delimiter=';'))
        row = next(row for row in rows if row[0] == 'CSV-01')
        self.assertTrue(row[1].startswith("'="))

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.request('/api/login', 'POST', dict(username='x', password='x'))[0], 401)
        self.assertEqual(self.request('/api/login', 'POST', dict(username='x', password='x'))[0], 429)


if __name__ == '__main__':
    unittest.main(verbosity=2)
