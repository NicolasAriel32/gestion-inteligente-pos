"""Invariantes de venta, permisos y concurrencia usando SQLite real aislado."""

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
from tests.test_catalog import adjust, create, write


def stock_product(client, csrf, stock=5, **changes):
    response = create(client, csrf, **{"code": None, "initial_stock": stock, "initial_reason": "Carga inicial", **changes})
    assert response.status_code == 201
    return response.json()


def intent(client, csrf, items, method="CASH", key=None):
    quote = write(client, csrf, "/api/sales/quote", {"items": items})
    assert quote.status_code == 200, quote.text
    return {"items": items, "payment_method": method, "idempotency_key": key or str(uuid4()), "quote_fingerprint": quote.json()["quote_fingerprint"]}


def buy(client, csrf, product, quantity=1, **kwargs):
    body = intent(client, csrf, [{"product_id": product["id"], "quantity": quantity}], **kwargs)
    return write(client, csrf, "/api/sales", body)


def dump(database):
    with sqlite3.connect(database) as db:
        return list(db.iterdump())


def test_sale_uses_server_prices_and_preserves_snapshots(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf, code="00017")
    response = buy(client, csrf, product, quantity=2, method="TRANSFER")
    assert response.status_code == 201
    sale = response.json()
    assert sale["total_cents"] == 25100
    assert sale["payment"] == {"method": "TRANSFER", "amount_cents": 25100}
    assert sale["items"][0]["product_name_snapshot"] == "Alfajor"
    assert sale["items"][0]["product_code_snapshot"] == "00017"
    assert "request_hash" not in sale and "idempotency_key" not in sale
    write(client, csrf, f"/api/products/{product['id']}", {"name": "Nombre nuevo", "code": "new", "price_cents": 100, "is_active": False}, "patch")
    assert client.get(f"/api/sales/{sale['id']}").json() == sale
    assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 3
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT quantity_delta,stock_before,stock_after,reference_type,reference_id FROM stock_movements WHERE movement_type='SALE'").fetchall() == [(-2, 5, 3, "SALE", sale["id"])]
        assert db.execute("SELECT action,actor_id,entity_type,entity_id FROM audit_events WHERE action='SALE_COMPLETED'").fetchall() == [("SALE_COMPLETED", 1, "sales", sale["id"])]


@pytest.mark.parametrize("items", [[], [{"product_id": 1, "quantity": 0}], [{"product_id": 1, "quantity": -1}], [{"product_id": True, "quantity": 1}], [{"product_id": 1, "quantity": True}], [{"product_id": 1, "quantity": 1.5}], [{"product_id": 1, "quantity": MAX_INTEGER + 1}], [{"product_id": 1, "quantity": 1}, {"product_id": 1, "quantity": 2}]])
def test_invalid_carts_are_rejected_without_writes(admin, database, items):
    client, csrf = admin
    before = dump(database)
    assert write(client, csrf, "/api/sales/quote", {"items": items}).status_code == 422
    assert dump(database) == before


@pytest.mark.parametrize("changes", [{"total_cents": 1}, {"user_id": 99}, {"status": "VOIDED"}, {"payment_method": "ONLINE"}, {"idempotency_key": "bad"}, {"quote_fingerprint": "bad"}])
def test_manipulated_checkout_contract_is_rejected(admin, database, changes):
    client, csrf = admin
    product = stock_product(client, csrf)
    body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    before = dump(database)
    assert write(client, csrf, "/api/sales", {**body, **changes}).status_code == 422
    assert dump(database) == before


def test_stale_quote_requires_review_and_client_cannot_set_unit_price(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    write(client, csrf, f"/api/products/{product['id']}", {"price_cents": 1}, "patch")
    before = dump(database)
    response = write(client, csrf, "/api/sales", body)
    assert response.status_code == 409 and "catálogo cambió" in response.json()["detail"]
    assert dump(database) == before
    assert write(client, csrf, "/api/sales/quote", {"items": [{"product_id": product["id"], "quantity": 1, "unit_price_cents": 0}]}).status_code == 422
    assert buy(client, csrf, product).json()["total_cents"] == 1


def test_insufficient_stock_inactive_product_and_overflow_have_no_partial_sale(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf, stock=1)
    body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    adjust(client, csrf, product["id"], -1)
    before = dump(database)
    assert write(client, csrf, "/api/sales", body).status_code == 409
    assert dump(database) == before
    write(client, csrf, f"/api/products/{product['id']}", {"is_active": False}, "patch")
    assert write(client, csrf, "/api/sales/quote", {"items": [{"product_id": product["id"], "quantity": 1}]}).status_code == 409
    expensive = stock_product(client, csrf, price_cents=MAX_INTEGER)
    before = dump(database)
    assert write(client, csrf, "/api/sales/quote", {"items": [{"product_id": expensive["id"], "quantity": 2}]}).status_code == 422
    assert dump(database) == before


def test_multiple_lines_total_and_zero_price(admin):
    client, csrf = admin
    one = stock_product(client, csrf, price_cents=29)
    two = stock_product(client, csrf, price_cents=0)
    body = intent(client, csrf, [{"product_id": one["id"], "quantity": 3}, {"product_id": two["id"], "quantity": 2}])
    sale = write(client, csrf, "/api/sales", body).json()
    assert sale["total_cents"] == 87 and len(sale["items"]) == 2
    assert sale["payment"]["amount_cents"] == 87
    assert write(client, csrf, "/api/sales", {**body, "items": list(reversed(body["items"]))}).json() == sale


def test_idempotent_replay_after_catalog_change_and_void(admin):
    client, csrf = admin
    product = stock_product(client, csrf)
    body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    first = write(client, csrf, "/api/sales", body).json()
    write(client, csrf, f"/api/products/{product['id']}", {"price_cents": 1, "is_active": False}, "patch")
    assert write(client, csrf, "/api/sales", body).json() == first
    assert write(client, csrf, "/api/sales", {**body, "payment_method": "CREDIT"}).status_code == 409
    voided = write(client, csrf, f"/api/sales/{first['id']}/void", {"reason": "Error de carga"}).json()
    assert write(client, csrf, "/api/sales", body).json() == voided
    assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 5


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_sales_last_unit_and_duplicate_key(admin, database, same_key):
    client, csrf = admin
    product = stock_product(client, csrf, stock=1)
    first = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    second = {**first, "idempotency_key": first["idempotency_key"] if same_key else str(uuid4())}
    barrier = Barrier(2)
    def send(body):
        barrier.wait()
        return write(client, csrf, "/api/sales", body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, [first, second]))
    assert sorted(r.status_code for r in responses) == ([201, 201] if same_key else [201, 409])
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM sales").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM payments").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type='SALE'").fetchone() == (1,)
        assert db.execute("SELECT stock_quantity FROM products").fetchone() == (0,)


@pytest.mark.parametrize("stage", ["payments", "stock_movements", "audit_events", "second_product"])
def test_mid_sale_failure_rolls_back_every_table(admin, database, stage):
    client, csrf = admin
    one, two = stock_product(client, csrf), stock_product(client, csrf)
    body = intent(client, csrf, [{"product_id": one["id"], "quantity": 1}, {"product_id": two["id"], "quantity": 1}])
    sql = (f"CREATE TRIGGER reject_stage BEFORE UPDATE ON products WHEN NEW.id={two['id']} BEGIN SELECT RAISE(ABORT,'sale rollback'); END" if stage == "second_product" else f"CREATE TRIGGER reject_stage BEFORE INSERT ON {stage} BEGIN SELECT RAISE(ABORT,'sale rollback'); END")
    with client.app.state.identity.store.engine.begin() as db:
        db.execute(text(sql))
    before = dump(database)
    with pytest.raises(IntegrityError):
        write(client, csrf, "/api/sales", body)
    assert dump(database) == before


def test_void_is_atomic_idempotent_and_preserves_history(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    sale = buy(client, csrf, product, 2).json()
    write(client, csrf, f"/api/products/{product['id']}", {"is_active": False}, "patch")
    responses = [write(client, csrf, f"/api/sales/{sale['id']}/void", {"reason": "Error de cobro"}) for _ in range(2)]
    assert responses[0].status_code == responses[1].status_code == 200
    assert responses[0].json() == responses[1].json()
    voided = responses[0].json()
    assert voided["status"] == "VOIDED" and voided["voided_by"] == 1
    assert voided["items"] == sale["items"] and voided["payment"] == sale["payment"]
    assert write(client, csrf, f"/api/sales/{sale['id']}/void", {"reason": "Otro motivo"}).status_code == 409
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT stock_quantity,is_active FROM products").fetchone() == (5, 0)
        assert db.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type='VOID'").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE action='SALE_VOIDED'").fetchone() == (1,)


def test_concurrent_void_is_applied_once(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    sale = buy(client, csrf, product).json()
    barrier = Barrier(2)
    def send(_):
        barrier.wait()
        return write(client, csrf, f"/api/sales/{sale['id']}/void", {"reason": "Error de carga"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT stock_quantity FROM products").fetchone() == (5,)
        assert db.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type='VOID'").fetchone() == (1,)


def test_void_failure_and_overflow_preserve_completed_sale(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    sale = buy(client, csrf, product).json()
    with client.app.state.identity.store.engine.begin() as db:
        db.execute(text("CREATE TRIGGER reject_void BEFORE INSERT ON audit_events WHEN NEW.action='SALE_VOIDED' BEGIN SELECT RAISE(ABORT,'void rollback'); END"))
    before = dump(database)
    with pytest.raises(IntegrityError):
        write(client, csrf, f"/api/sales/{sale['id']}/void", {"reason": "Error de carga"})
    assert dump(database) == before
    with client.app.state.identity.store.engine.begin() as db:
        db.execute(text("DROP TRIGGER reject_void"))
    assert adjust(client, csrf, product["id"], MAX_INTEGER - 4).status_code == 201
    before = dump(database)
    assert write(client, csrf, f"/api/sales/{sale['id']}/void", {"reason": "Error de carga"}).status_code == 409
    assert dump(database) == before


def test_employee_can_sell_but_cannot_read_other_sales_or_void(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    owner_body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    owner_sale = write(client, csrf, "/api/sales", owner_body).json()
    write(client, csrf, "/api/employees", {"username": "worker", "password": PASSWORD})
    with TestClient(create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}) as worker:
        worker_csrf = login(worker, "worker")
        worker_sale = buy(worker, worker_csrf, product).json()
        assert worker_sale["username_snapshot"] == "worker"
        assert worker.get("/api/sales").json()["total"] == 1
        assert worker.get(f"/api/sales/{owner_sale['id']}").status_code == 403
        assert worker.get("/api/sales?user_id=1").status_code == 403
        assert write(worker, worker_csrf, f"/api/sales/{worker_sale['id']}/void", {"reason": "No permitido"}).status_code == 403
        assert write(worker, worker_csrf, "/api/sales", owner_body).status_code == 409
        assert client.get("/api/sales").json()["total"] == 2
        assert client.get(f"/api/sales?user_id={worker_sale['user_id']}").json()["total"] == 1
        write(client, csrf, f"/api/employees/{worker_sale['user_id']}", {"is_active": False}, "patch")
        assert worker.get("/api/sales").status_code == 401


def test_sale_security_csrf_expiry_and_restart(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    items = [{"product_id": product["id"], "quantity": 1}]
    assert client.post("/api/sales/quote", json={"items": items}).status_code == 403
    with TestClient(create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}) as anonymous:
        assert anonymous.get("/api/sales").status_code == 401
    sale = buy(client, csrf, product).json()
    with TestClient(create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN, "cookie": f"pos_session={client.cookies.get('pos_session')}"}) as restarted:
        assert restarted.get(f"/api/sales/{sale['id']}").json() == sale
    client.app.state.identity.clock = lambda: 9_999_999_999
    assert write(client, csrf, "/api/sales/quote", {"items": items}).status_code == 401


def test_database_enforces_historical_integrity(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    sale = buy(client, csrf, product).json()
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for sql in ["UPDATE sale_items SET unit_price_cents=0", "DELETE FROM sale_items", "UPDATE payments SET amount_cents=0", "DELETE FROM payments", "UPDATE sales SET total_cents=0", "DELETE FROM sales", "DELETE FROM products", "UPDATE sales SET status='VOIDED',voided_by=1,voided_at_utc='2026-10-22'", "INSERT INTO sale_items(sale_id,product_id,product_name_snapshot,unit_price_cents,quantity,subtotal_cents) VALUES(1,1,'extra',1,1,1)"]:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
            db.rollback()
    assert client.get(f"/api/sales/{sale['id']}").json() == sale


def test_history_filters_and_invalid_pagination(admin):
    client, csrf = admin
    product = stock_product(client, csrf)
    one = buy(client, csrf, product).json()
    buy(client, csrf, product, method="DEBIT")
    write(client, csrf, f"/api/sales/{one['id']}/void", {"reason": "Error de carga"})
    assert client.get("/api/sales?status=COMPLETED").json()["total"] == 1
    assert client.get("/api/sales?status=VOIDED").json()["total"] == 1
    page = client.get("/api/sales?limit=1&offset=1").json()
    assert page["total"] == 2 and page["items"][0]["id"] == one["id"]
    assert client.get("/api/sales?limit=101").status_code == 422
    assert client.get("/api/sales?offset=-1").status_code == 422
    assert client.get("/api/sales/0").status_code == 422


@pytest.mark.parametrize("method", ["CASH", "TRANSFER", "DEBIT", "CREDIT"])
def test_each_manual_payment_method_has_one_payment(admin, database, method):
    client, csrf = admin
    product = stock_product(client, csrf)
    sale = buy(client, csrf, product, method=method)
    assert sale.status_code == 201 and sale.json()["payment"]["method"] == method
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM payments").fetchone() == (1,)


def test_sale_competes_with_manual_adjustment_for_last_unit(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf, stock=1)
    body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
    barrier = Barrier(2)
    def act(kind):
        barrier.wait()
        return write(client, csrf, "/api/sales", body) if kind == "sale" else adjust(client, csrf, product["id"], -1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(act, ["sale", "adjust"]))
    assert sorted(r.status_code for r in responses) == [201, 409]
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT stock_quantity FROM products").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type IN ('SALE','ADJUSTMENT')").fetchone() == (1,)


def test_void_and_manual_adjustment_serialize_stock(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf, stock=1)
    sale = buy(client, csrf, product).json()
    barrier = Barrier(2)
    def act(kind):
        barrier.wait()
        return write(client, csrf, f"/api/sales/{sale['id']}/void", {"reason": "Error de carga"}) if kind == "void" else adjust(client, csrf, product["id"], 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(act, ["void", "adjust"]))
    assert sorted(r.status_code for r in responses) == [200, 201]
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT stock_quantity FROM products").fetchone() == (2,)
        rows = db.execute("SELECT stock_before,stock_after FROM stock_movements ORDER BY id").fetchall()
        assert rows[-2:] == [(0, 1), (1, 2)]


def test_empty_too_large_and_multi_line_overflow_carts(admin, database):
    client, csrf = admin
    assert write(client, csrf, "/api/sales/quote", {"items": [{"product_id": i + 1, "quantity": 1} for i in range(101)]}).status_code == 422
    one = stock_product(client, csrf, price_cents=MAX_INTEGER)
    two = stock_product(client, csrf, price_cents=1)
    before = dump(database)
    assert write(client, csrf, "/api/sales/quote", {"items": [{"product_id": one["id"], "quantity": 1}, {"product_id": two["id"], "quantity": 1}]}).status_code == 422
    assert dump(database) == before
