"""Catálogo e inventario contra SQLite real, sin datos de instalaciones existentes."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domain.catalog import MAX_INTEGER
from app.main import create_app
from tests.conftest import ORIGIN, PASSWORD, login


def write(client, csrf, path, data, method="post"):
    return getattr(client, method)(path, json=data, headers={"x-csrf-token": csrf})


def create(client, csrf, **changes):
    return write(
        client,
        csrf,
        "/api/products",
        {"name": "Alfajor", "code": "00123", "price_cents": 12550, **changes},
    )


def adjust(client, csrf, product_id, delta, key=None):
    return write(
        client,
        csrf,
        "/api/stock/adjustments",
        {
            "product_id": product_id,
            "quantity_delta": delta,
            "reason": "Conteo físico",
            "idempotency_key": key or str(uuid4()),
        },
    )


def test_categories_products_and_integer_money(admin):
    client, csrf = admin
    cat = write(client, csrf, "/api/categories", {"name": " Bebidas "})
    assert cat.status_code == 201 and cat.json()["name"] == "Bebidas"
    assert write(client, csrf, "/api/categories", {"name": "BEBIDAS"}).status_code == 409
    product = create(
        client,
        csrf,
        category_id=cat.json()["id"],
        cost_cents=10000,
        initial_stock=2,
        initial_reason="Carga inicial",
    )
    assert product.status_code == 201
    data = product.json()
    assert (data["code"], data["price_cents"], data["stock_quantity"]) == ("00123", 12550, 2)
    assert create(client, csrf).status_code == 409
    assert create(client, csrf, code=None).status_code == 201
    assert create(client, csrf, code="").status_code == 201
    movements = client.get("/api/stock/movements").json()["items"]
    assert len(movements) == 1
    assert (
        movements[0]["stock_before"],
        movements[0]["stock_after"],
        movements[0]["performed_by"],
    ) == (0, 2, 1)
    assert movements[0]["movement_type"] == "INITIAL"
    assert (
        write(
            client,
            csrf,
            f"/api/products/{data['id']}",
            {"price_cents": 15001, "code": None},
            "patch",
        ).json()["price_cents"]
        == 15001
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"price_cents": -1},
        {"price_cents": 1.5},
        {"price_cents": True},
        {"price_cents": MAX_INTEGER + 1},
        {"minimum_stock": -1},
        {"initial_stock": -1},
        {"initial_stock": 1.1},
        {"initial_stock": True},
        {"initial_stock": 1},
        {"name": "  "},
        {"code": 123},
        {"cost_cents": -1},
        {"stock_quantity": 4},
    ],
)
def test_invalid_product_data_rejected_without_rows(admin, changes, database):
    client, csrf = admin
    assert create(client, csrf, **changes).status_code == 422
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM products").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM stock_movements").fetchone() == (0,)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"stock_quantity": 7},
        {"name": None},
        {"price_cents": None},
        {"minimum_stock": -1},
        {"is_active": 1},
    ],
)
def test_invalid_patch_does_not_change_product(admin, payload):
    client, csrf = admin
    product = create(client, csrf).json()
    assert (
        write(client, csrf, f"/api/products/{product['id']}", payload, "patch").status_code == 422
    )
    assert client.get(f"/api/products/{product['id']}").json() == product


def test_adjustment_idempotency_and_negative_guard(admin, database):
    client, csrf = admin
    product = create(client, csrf, initial_stock=2, initial_reason="Carga inicial").json()
    key = str(uuid4())
    first = adjust(client, csrf, product["id"], -1, key)
    assert first.status_code == 201
    assert adjust(client, csrf, product["id"], -1, key).json() == first.json()
    assert adjust(client, csrf, product["id"], 1, key).status_code == 409
    assert adjust(client, csrf, product["id"], -2).status_code == 409
    assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 1
    with sqlite3.connect(database) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE movement_type='ADJUSTMENT'"
        ).fetchone() == (1,)
        assert db.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action='STOCK_ADJUSTED'"
        ).fetchone() == (1,)


@pytest.mark.parametrize("delta", [0, 1.5, True, MAX_INTEGER + 1])
def test_adjustment_rejects_invalid_delta(admin, delta):
    client, csrf = admin
    product = create(client, csrf).json()
    assert adjust(client, csrf, product["id"], delta).status_code == 422


def test_adjustment_requires_reason_and_rejects_overflow(admin):
    client, csrf = admin
    product = create(client, csrf, initial_stock=MAX_INTEGER, initial_reason="Carga inicial").json()
    assert adjust(client, csrf, product["id"], 1).status_code == 422
    assert (
        write(
            client,
            csrf,
            "/api/stock/adjustments",
            {
                "product_id": product["id"],
                "quantity_delta": 1,
                "reason": " ",
                "idempotency_key": str(uuid4()),
            },
        ).status_code
        == 422
    )


def test_concurrent_adjustments_never_go_negative(admin, database):
    client, csrf = admin
    product = create(client, csrf, initial_stock=1, initial_reason="Carga inicial").json()
    cookie = client.cookies.get("pos_session")
    barrier = Barrier(2)

    def attempt(_):
        with TestClient(
            create_app(database),
            base_url="http://127.0.0.1",
            headers={"origin": ORIGIN, "cookie": f"pos_session={cookie}"},
        ) as worker:
            barrier.wait(timeout=10)
            return adjust(worker, csrf, product["id"], -1).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [201, 409]
    assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 0


def test_concurrent_same_key_applies_once(admin, database):
    client, csrf = admin
    product = create(client, csrf).json()
    cookie = client.cookies.get("pos_session")
    key, barrier = str(uuid4()), Barrier(2)

    def attempt(_):
        with TestClient(
            create_app(database),
            base_url="http://127.0.0.1",
            headers={"origin": ORIGIN, "cookie": f"pos_session={cookie}"},
        ) as worker:
            barrier.wait(timeout=10)
            return adjust(worker, csrf, product["id"], 3, key).json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(attempt, range(2)))) == 1
    assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 3


def test_audit_failure_rolls_back_stock_and_movement(admin, database):
    client, csrf = admin
    product = create(client, csrf, initial_stock=2, initial_reason="Carga inicial").json()
    with client.app.state.identity.store.engine.begin() as connection:
        connection.execute(
            text("""CREATE TRIGGER reject_stock_audit BEFORE INSERT ON audit_events
          WHEN NEW.action='STOCK_ADJUSTED' BEGIN SELECT RAISE(ABORT, 'rollback test'); END""")
        )
    with pytest.raises(IntegrityError):
        adjust(client, csrf, product["id"], -1)
    assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 2
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM stock_movements").fetchone() == (1,)


def test_product_creation_rolls_back_when_audit_fails(admin, database):
    client, csrf = admin
    with client.app.state.identity.store.engine.begin() as connection:
        connection.execute(
            text("""CREATE TRIGGER reject_product BEFORE INSERT ON audit_events
          WHEN NEW.action='PRODUCT_CREATED' BEGIN SELECT RAISE(ABORT, 'rollback test'); END""")
        )
    with pytest.raises(IntegrityError):
        create(client, csrf, initial_stock=2, initial_reason="Carga inicial")
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM products").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM stock_movements").fetchone() == (0,)


def test_soft_deactivation_and_category_rules(admin):
    client, csrf = admin
    category = write(client, csrf, "/api/categories", {"name": "Golosinas"}).json()
    product = create(client, csrf, category_id=category["id"]).json()
    assert (
        write(
            client, csrf, f"/api/categories/{category['id']}", {"is_active": False}, "patch"
        ).status_code
        == 200
    )
    assert create(client, csrf, code=None, category_id=category["id"]).status_code == 409
    assert (
        write(
            client, csrf, f"/api/products/{product['id']}", {"name": "Alfajor nuevo"}, "patch"
        ).status_code
        == 200
    )
    assert (
        write(
            client, csrf, f"/api/products/{product['id']}", {"is_active": False}, "patch"
        ).status_code
        == 200
    )
    assert adjust(client, csrf, product["id"], 1).status_code == 409
    assert client.get("/api/products").json()["total"] == 0
    assert client.get("/api/products?active_only=false").json()["total"] == 1
    assert (
        client.request(
            "DELETE", f"/api/products/{product['id']}", json={}, headers={"x-csrf-token": csrf}
        ).status_code
        == 405
    )
    assert (
        write(
            client, csrf, f"/api/products/{product['id']}", {"is_active": True}, "patch"
        ).status_code
        == 200
    )


def test_employee_reads_active_catalog_without_cost_and_cannot_write(admin, database):
    client, csrf = admin
    category = write(client, csrf, "/api/categories", {"name": "Bebidas"}).json()
    product = create(client, csrf, category_id=category["id"], cost_cents=8000).json()
    inactive = create(client, csrf, code="different").json()
    write(client, csrf, f"/api/products/{inactive['id']}", {"is_active": False}, "patch")
    write(client, csrf, "/api/employees", {"username": "worker", "password": PASSWORD})
    with TestClient(
        create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}
    ) as worker:
        worker_csrf = login(worker, "worker")
        items = worker.get("/api/products?active_only=false").json()["items"]
        assert len(items) == 1 and items[0]["cost_cents"] is None
        assert worker.get(f"/api/products/{product['id']}").json()["cost_cents"] is None
        assert worker.get(f"/api/products/{inactive['id']}").status_code == 404
        assert worker.get("/api/stock/movements").status_code == 403
        assert create(worker, worker_csrf, code=None).status_code == 403
        assert adjust(worker, worker_csrf, product["id"], 1).status_code == 403
        assert (
            write(worker, worker_csrf, "/api/categories", {"name": "No permitido"}).status_code
            == 403
        )
        assert (
            write(
                worker, worker_csrf, f"/api/products/{product['id']}", {"price_cents": 0}, "patch"
            ).status_code
            == 403
        )
        assert (
            write(
                worker,
                worker_csrf,
                f"/api/categories/{category['id']}",
                {"is_active": False},
                "patch",
            ).status_code
            == 403
        )


def test_search_filters_pagination_and_sql_text(admin):
    client, csrf = admin
    category = write(client, csrf, "/api/categories", {"name": "Bebidas"}).json()
    create(client, csrf, name="ÁGUA", code="ABC001", category_id=category["id"], minimum_stock=1)
    create(
        client,
        csrf,
        name="Otro ' producto",
        code=None,
        initial_stock=5,
        initial_reason="Carga inicial",
    )
    assert client.get("/api/products?search=água").json()["total"] == 1
    assert client.get("/api/products?search=ABC001").json()["total"] == 1
    assert client.get("/api/products?search=%27").json()["total"] == 1
    assert client.get("/api/products?limit=1").json()["total"] == 2
    assert len(client.get("/api/products?limit=1&offset=1").json()["items"]) == 1
    assert client.get("/api/products?low_stock=true").json()["total"] == 1
    assert client.get(f"/api/products?category_id={category['id']}").json()["total"] == 1
    assert client.get("/api/products?limit=101").status_code == 422
    assert client.get("/api/products?offset=-1").status_code == 422
    assert write(client, csrf, "/api/categories/0", {"name": "bad"}, "patch").status_code == 422


def test_sqlite_checks_and_foreign_keys_are_real(admin, database):
    client, csrf = admin
    product = create(client, csrf).json()
    movement = adjust(client, csrf, product["id"], 1).json()
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for sql, params in [
            ("UPDATE products SET stock_quantity=-1 WHERE id=?", (product["id"],)),
            ("UPDATE products SET price_cents=1.1 WHERE id=?", (product["id"],)),
            ("UPDATE products SET category_id=999 WHERE id=?", (product["id"],)),
            ("UPDATE products SET price_cents=9007199254740992 WHERE id=?", (product["id"],)),
            ("UPDATE stock_movements SET stock_before=9007199254740992,quantity_delta=-9007199254740991 WHERE id=?", (movement["id"],)),
            ("UPDATE stock_movements SET stock_before=9007199254740991,quantity_delta=-9007199254740992,stock_after=0 WHERE id=?", (movement["id"],)),
        ]:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql, params)
            db.rollback()


def test_csrf_and_anonymous_access(admin, database):
    client, _csrf = admin
    assert client.post("/api/categories", json={"name": "bad"}).status_code == 403
    with TestClient(
        create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}
    ) as anonymous:
        assert anonymous.get("/api/products").status_code == 401
        assert anonymous.get("/api/categories").status_code == 401
        assert anonymous.get("/api/stock/movements").status_code == 401


def test_stock_persists_after_restart(admin, database):
    client, csrf = admin
    product = create(client, csrf).json()
    adjust(client, csrf, product["id"], 4)
    with TestClient(
        create_app(database),
        base_url="http://127.0.0.1",
        headers={"cookie": f"pos_session={client.cookies.get('pos_session')}"},
    ) as restarted:
        assert restarted.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 4
        assert restarted.get("/api/stock/movements").json()["items"][0]["stock_after"] == 4
