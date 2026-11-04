"""Persistência e regras de negócio. Valores monetários são centavos inteiros."""

import hashlib
import hmac
import os
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ValidationError(ValueError):
    pass


def text(value, label, limit=80):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValidationError(f"{label}: informe de 1 a {limit} caracteres.")
    return value.strip()


def integer(value, label, minimum=0):
    if isinstance(value, bool) or not re.fullmatch(r"\d{1,9}", str(value)):
        raise ValidationError(f"{label}: informe um número inteiro válido.")
    result = int(value)
    if result < minimum:
        raise ValidationError(f"{label}: o mínimo é {minimum}.")
    return result


def money(value):
    try:
        number = Decimal(str(value))
        if (
            not number.is_finite()
            or number < 0
            or number > 99999999
            or number.as_tuple().exponent < -2
        ):
            raise InvalidOperation
        return int(number * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(
            "Preço: informe um valor positivo com até duas casas decimais."
        ) from None


def hash_password(password):
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"{salt}:{digest}"


def check_password(password, encoded):
    salt, digest = encoded.split(":")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return hmac.compare_digest(actual, digest)


class Inventory:
    def __init__(self, path):
        self.path = str(path)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def initialize(self, password, demo=False):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript((ROOT / "database/schema.sql").read_text())
            db.execute("PRAGMA journal_mode=WAL")
            if not db.execute("SELECT id FROM users LIMIT 1").fetchone():
                db.execute(
                    "INSERT INTO users(username,password_hash) VALUES (?,?)",
                    ("admin", hash_password(password)),
                )
            empty_catalog = not any(
                db.execute(f"SELECT id FROM {table} LIMIT 1").fetchone()
                for table in ("categories", "suppliers", "products", "movements")
            )
            if demo and empty_catalog:
                db.executemany(
                    "INSERT INTO categories(name) VALUES (?)",
                    [("Escritório",), ("Tecnologia",), ("Embalagens",)],
                )
                db.executemany(
                    "INSERT INTO suppliers(name) VALUES (?)",
                    [("Distribuidora Exemplo",), ("Suprimentos Demo",)],
                )
                examples = [
                    ("TEC-001", "Mouse sem fio", 2, 1, 8990, 10, 32),
                    ("ESC-001", "Caderno A5", 1, 2, 2490, 15, 8),
                    ("EMB-001", "Caixa de papelão M", 3, 1, 650, 20, 54),
                    ("TEC-002", "Teclado USB", 2, 1, 12990, 5, 0),
                ]
                user_id = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()[0]
                for sku, name, cat, supplier, price, minimum, quantity in examples:
                    pid = db.execute(
                        "INSERT INTO products(sku,name,category_id,supplier_id,price_cents,minimum,quantity) VALUES (?,?,?,?,?,?,?)",
                        (sku, name, cat, supplier, price, minimum, quantity),
                    ).lastrowid
                    if quantity:
                        db.execute(
                            "INSERT INTO movements(product_id,user_id,kind,quantity,note,balance_after) VALUES (?,?,?,?,?,?)",
                            (
                                pid,
                                user_id,
                                "entrada",
                                quantity,
                                "Carga de demonstração",
                                quantity,
                            ),
                        )

    def authenticate(self, username, password):
        with self.connect() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if user and check_password(password, user["password_hash"]):
                return {"id": user["id"], "username": user["username"]}
        return None

    def register(self, data):
        username = text(data.get("username"), "Usuário", 32).lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,31}", username):
            raise ValidationError(
                "Usuário: use de 3 a 32 letras sem acentos, números, ponto, hífen ou sublinhado."
            )
        password = data.get("password")
        if not isinstance(password, str) or not 8 <= len(password) <= 256:
            raise ValidationError("Senha: use de 8 a 256 caracteres.")
        if password != data.get("confirm_password"):
            raise ValidationError("As senhas não coincidem.")
        with self.connect() as db:
            if db.execute("SELECT id FROM users WHERE lower(username)=?", (username,)).fetchone():
                raise ValidationError(
                    "Este usuário já está cadastrado. Escolha outro nome ou entre na sua conta."
                )
            uid = db.execute(
                "INSERT INTO users(username,password_hash) VALUES (?,?)",
                (username, hash_password(password)),
            ).lastrowid
        return {"id": uid, "username": username}

    def configure_demo_access(self, reset=False):
        """Migra só a senha demo antiga; outras senhas exigem reset local explícito."""
        with self.connect() as db:
            user = db.execute(
                "SELECT id,password_hash FROM users WHERE username='admin'"
            ).fetchone()
            if user and (reset or check_password("EstoquePro@2026", user["password_hash"])):
                db.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (hash_password("admin123"), user["id"]),
                )
                return True
        return False

    def lookup(self, table):
        assert table in ("categories", "suppliers")
        with self.connect() as db:
            return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY name")]

    def add_lookup(self, table, data):
        assert table in ("categories", "suppliers")
        name = text(data.get("name"), "Nome")
        with self.connect() as db:
            return db.execute(f"INSERT INTO {table}(name) VALUES (?)", (name,)).lastrowid

    def products(self, query="", category="", low=False):
        sql = """SELECT p.*, c.name category, s.name supplier FROM products p
                 JOIN categories c ON c.id=p.category_id LEFT JOIN suppliers s ON s.id=p.supplier_id
                 WHERE p.active=1"""
        args = []
        if query:
            sql += " AND (instr(lower(p.name),lower(?))>0 OR instr(lower(p.sku),lower(?))>0)"
            args += [query, query]
        if category:
            sql += " AND p.category_id=?"
            args.append(integer(category, "Categoria", 1))
        if low:
            sql += " AND p.quantity<=p.minimum"
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql + " ORDER BY p.name", args)]

    def save_product(self, data, product_id=None):
        sku = text(data.get("sku"), "Código", 32).upper()
        name = text(data.get("name"), "Nome", 120)
        category = integer(data.get("category_id"), "Categoria", 1)
        supplier = (
            integer(data["supplier_id"], "Fornecedor", 1) if data.get("supplier_id") else None
        )
        price = money(data.get("price"))
        minimum = integer(data.get("minimum"), "Estoque mínimo")
        with self.connect() as db:
            if not db.execute("SELECT id FROM categories WHERE id=?", (category,)).fetchone():
                raise ValidationError("Categoria não encontrada.")
            if (
                supplier
                and not db.execute("SELECT id FROM suppliers WHERE id=?", (supplier,)).fetchone()
            ):
                raise ValidationError("Fornecedor não encontrado.")
            values = (sku, name, category, supplier, price, minimum)
            if product_id is None:
                return db.execute(
                    "INSERT INTO products(sku,name,category_id,supplier_id,price_cents,minimum) VALUES (?,?,?,?,?,?)",
                    values,
                ).lastrowid
            result = db.execute(
                "UPDATE products SET sku=?,name=?,category_id=?,supplier_id=?,price_cents=?,minimum=? WHERE id=? AND active=1",
                values + (product_id,),
            )
            if not result.rowcount:
                raise ValidationError("Produto não encontrado.")
            return product_id

    def archive(self, product_id):
        with self.connect() as db:
            result = db.execute(
                "UPDATE products SET active=0 WHERE id=? AND active=1 AND quantity=0",
                (product_id,),
            )
            if not result.rowcount:
                raise ValidationError("Só é possível arquivar um produto ativo com saldo zero.")

    def move(self, data, user_id):
        pid = integer(data.get("product_id"), "Produto", 1)
        quantity = integer(data.get("quantity"), "Quantidade", 1)
        kind = data.get("kind")
        if kind not in ("entrada", "saida"):
            raise ValidationError("Tipo de movimentação inválido.")
        note = text(data.get("note"), "Motivo", 240)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT quantity FROM products WHERE id=? AND active=1", (pid,)
            ).fetchone()
            if not row:
                raise ValidationError("Produto não encontrado ou arquivado.")
            balance = row["quantity"] + (quantity if kind == "entrada" else -quantity)
            if balance < 0:
                raise ValidationError("Saldo insuficiente para esta saída.")
            if balance > 999999999:
                raise ValidationError("Saldo máximo permitido: 999999999.")
            db.execute("UPDATE products SET quantity=? WHERE id=?", (balance, pid))
            return db.execute(
                "INSERT INTO movements(product_id,user_id,kind,quantity,note,balance_after) VALUES (?,?,?,?,?,?)",
                (pid, user_id, kind, quantity, note, balance),
            ).lastrowid

    def movements(self):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute("""SELECT m.*, p.name product, p.sku, u.username
                FROM movements m JOIN products p ON m.product_id=p.id JOIN users u ON m.user_id=u.id
                ORDER BY m.id DESC LIMIT 200""")
            ]

    def dashboard(self):
        with self.connect() as db:
            return dict(
                db.execute("""SELECT count(*) products, coalesce(sum(quantity),0) units,
                coalesce(sum(quantity*price_cents),0) value_cents,
                coalesce(sum(quantity<=minimum),0) low FROM products WHERE active=1""").fetchone()
            )
