import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path

from legacy.estoquepro.domain import (
    Inventory,
    ValidationError,
    check_password,
    hash_password,
    money,
)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.db = Inventory(self.path)
        self.db.initialize("UmaSenhaForte123")
        self.category = self.db.add_lookup("categories", {"name": "Categoria teste"})
        self.supplier = self.db.add_lookup("suppliers", {"name": "Fornecedor teste"})
        self.data = dict(
            sku="TEST-01",
            name="Produto teste",
            category_id=self.category,
            supplier_id=self.supplier,
            price="12.90",
            minimum=2,
        )
        self.pid = self.db.save_product(self.data)
        self.uid = self.db.authenticate("admin", "UmaSenhaForte123")["id"]

    def tearDown(self):
        self.temp.cleanup()

    def move(self, kind, quantity, pid=None):
        return self.db.move(
            dict(
                product_id=pid or self.pid,
                kind=kind,
                quantity=quantity,
                note="Teste de movimentação",
            ),
            self.uid,
        )

    def test_authentication_and_hash(self):
        self.assertIsNone(self.db.authenticate("admin", "errada"))
        self.assertIsNone(self.db.authenticate("' OR 1=1 --", "errada"))
        encoded = hash_password("segredo")
        self.assertNotIn("segredo", encoded)
        self.assertTrue(check_password("segredo", encoded))
        self.assertFalse(check_password("outro", encoded))

    def test_register_validation_and_duplicate(self):
        data = dict(
            username="Novo.Usuario",
            password="SenhaNova123",
            confirm_password="SenhaNova123",
        )
        user = self.db.register(data)
        self.assertEqual(user["username"], "novo.usuario")
        self.assertEqual(self.db.authenticate("novo.usuario", "SenhaNova123"), user)
        with self.assertRaisesRegex(ValidationError, "já está cadastrado"):
            self.db.register(data)
        for changes in [
            dict(username="ab"),
            dict(username="nome com espaços"),
            dict(username="<script>"),
            dict(password="curta", confirm_password="curta"),
            dict(confirm_password="diferente"),
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.db.register({**data, "username": "outro.usuario", **changes})

    def test_legacy_demo_migration_preserves_data(self):
        with self.db.connect() as db:
            db.execute(
                "UPDATE users SET password_hash=? WHERE username='admin'",
                (hash_password("EstoquePro@2026"),),
            )
        before = self.db.products()
        self.assertTrue(self.db.configure_demo_access())
        self.assertIsNotNone(self.db.authenticate("admin", "admin123"))
        self.assertIsNone(self.db.authenticate("admin", "EstoquePro@2026"))
        self.assertEqual(self.db.products(), before)
        self.assertFalse(self.db.configure_demo_access())

    def test_demo_preserves_custom_password_until_explicit_reset(self):
        self.assertFalse(self.db.configure_demo_access())
        self.assertIsNotNone(self.db.authenticate("admin", "UmaSenhaForte123"))
        self.assertTrue(self.db.configure_demo_access(reset=True))
        self.assertIsNotNone(self.db.authenticate("admin", "admin123"))

    def test_product_create_update_search(self):
        product = self.db.products()[0]
        self.assertEqual(product["quantity"], 0)
        self.assertEqual(product["price_cents"], 1290)
        self.move("entrada", 7)
        self.db.save_product(dict(self.data, name="Nome atualizado", price="9.99"), self.pid)
        found = self.db.products("atualizado", str(self.category))
        self.assertEqual(found[0]["quantity"], 7)
        self.assertEqual(found[0]["price_cents"], 999)
        self.assertEqual(len(self.db.products("TEST-01")), 1)
        self.assertEqual(self.db.products("' OR 1=1 --"), [])

    def test_duplicate_sku_and_lookup(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.save_product(dict(self.data, sku="test-01"))
        for table, name in [
            ("categories", "categoria teste"),
            ("suppliers", "fornecedor teste"),
        ]:
            with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                self.db.add_lookup(table, {"name": name})

    def test_product_validation(self):
        for changes in [
            dict(name=" "),
            dict(sku=""),
            dict(category_id=999),
            dict(supplier_id=999),
            dict(minimum=-1),
            dict(minimum=1.5),
            dict(price="NaN"),
            dict(price="1.234"),
            dict(price="-1"),
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.db.save_product(dict(self.data, **changes))
        with self.assertRaises(ValidationError):
            self.db.save_product(self.data, 999)

    def test_money_exactness(self):
        self.assertEqual(money("0.29"), 29)
        self.assertEqual(money("123.45"), 12345)

    def test_entry_exit_and_persistence(self):
        self.move("entrada", 10)
        self.move("saida", 3)
        reopened = Inventory(self.path)
        self.assertEqual(reopened.products()[0]["quantity"], 7)
        history = reopened.movements()
        self.assertEqual([m["balance_after"] for m in history], [7, 10])
        self.assertEqual(history[0]["username"], "admin")
        self.assertEqual(history[0]["note"], "Teste de movimentação")

    def test_insufficient_balance_rolls_back(self):
        self.move("entrada", 3)
        with self.assertRaisesRegex(ValidationError, "insuficiente"):
            self.move("saida", 4)
        self.assertEqual(self.db.products()[0]["quantity"], 3)
        self.assertEqual(len(self.db.movements()), 1)

    def test_movement_validation(self):
        for changes in [
            dict(quantity=0),
            dict(quantity=-2),
            dict(quantity=1.2),
            dict(quantity=True),
            dict(kind="ajuste"),
            dict(note=""),
            dict(product_id=999),
        ]:
            data = dict(product_id=self.pid, kind="entrada", quantity=1, note="Teste")
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.db.move(dict(data, **changes), self.uid)
        self.assertEqual(self.db.movements(), [])

    def test_maximum_balance(self):
        self.move("entrada", 999999999)
        with self.assertRaises(ValidationError):
            self.move("entrada", 1)
        self.assertEqual(self.db.products()[0]["quantity"], 999999999)

    def test_archive_preserves_history_and_reserved_sku(self):
        self.move("entrada", 2)
        with self.assertRaises(ValidationError):
            self.db.archive(self.pid)
        self.move("saida", 2)
        self.db.archive(self.pid)
        self.assertEqual(self.db.products(), [])
        self.assertEqual(len(self.db.movements()), 2)
        with self.assertRaises(ValidationError):
            self.move("entrada", 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.save_product(self.data)

    def test_dashboard_and_low_filter(self):
        self.move("entrada", 2)
        self.assertEqual(self.db.dashboard(), dict(products=1, units=2, value_cents=2580, low=1))
        self.assertEqual(len(self.db.products(low=True)), 1)
        self.move("entrada", 1)
        self.assertEqual(self.db.products(low=True), [])

    def test_concurrent_exits_are_atomic(self):
        self.move("entrada", 5)

        def attempt(_):
            try:
                self.move("saida", 4)
                return True
            except ValidationError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.db.products()[0]["quantity"], 1)
        self.assertEqual(len(self.db.movements()), 2)

    def test_initialization_repeatable_and_demo(self):
        demo_path = Path(self.temp.name) / "demo.sqlite3"
        demo = Inventory(demo_path)
        demo.initialize("senha-demo", demo=True)
        original = demo.dashboard()
        demo.initialize("outra-senha", demo=True)
        self.assertEqual(demo.dashboard(), original)
        self.assertEqual(original["products"], 4)
        self.assertEqual(original["units"], 94)
        self.assertIsNotNone(demo.authenticate("admin", "senha-demo"))
        with demo.connect() as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_demo_preserves_partially_configured_catalog(self):
        inventory = Inventory(Path(self.temp.name) / "partial.sqlite3")
        inventory.initialize("senha-local")
        inventory.add_lookup("suppliers", {"name": "Fornecedor cadastrado pelo usuário"})
        inventory.initialize("outra-senha", demo=True)
        self.assertEqual(len(inventory.lookup("suppliers")), 1)
        self.assertEqual(inventory.lookup("categories"), [])
        self.assertEqual(inventory.products(), [])
