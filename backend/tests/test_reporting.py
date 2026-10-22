"""F5: calendario, exactitud, historia y snapshot sobre SQLite real."""

import sqlite3
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.domain.catalog import MAX_INTEGER
from app.domain.identity import IdentityError
from app.domain.reporting import comparison, periods, rounded
from app.infrastructure.reporting import ReportingTransaction
from tests.conftest import PASSWORD, login
from tests.test_catalog import write
from tests.test_sales import buy, stock_product


def seed(database, product, stamp, price=101, quantity=1, user=1, name="Histórico"):
    # Datos ficticios, estructura sellada con pago como el caso de uso; no editar historia.
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        sale = db.execute("INSERT INTO sales(idempotency_key,request_hash,user_id,username_snapshot,total_cents,created_at_utc) VALUES(?,?,?,?,?,?)", (str(uuid4()), "a" * 64, user, "vendedor histórico", price * quantity, stamp)).lastrowid
        db.execute("INSERT INTO sale_items(sale_id,product_id,product_name_snapshot,product_code_snapshot,unit_price_cents,quantity,subtotal_cents) VALUES(?,?,?,?,?,?,?)", (sale, product, name, "0001", price, quantity, price * quantity))
        db.execute("INSERT INTO payments(sale_id,method,amount_cents) VALUES(?,'CASH',?)", (sale, price * quantity))
        return sale


def fixed(client, stamp="2026-01-01T15:00:00+00:00"):
    client.app.state.identity.clock = lambda: datetime.fromisoformat(stamp).timestamp()


def test_report_known_multiline_void_and_historical_inactive(admin):
    client, csrf = admin
    # Login clock remains real for sessions; reports use an independent fixed clock.
    client.app.state.reporting.clock = lambda: datetime.now(UTC).timestamp()
    one = stock_product(client, csrf, price_cents=101)
    two = stock_product(client, csrf, price_cents=50)
    from tests.test_sales import intent
    sale = write(client, csrf, "/api/sales", intent(client, csrf, [{"product_id": one["id"], "quantity": 2}, {"product_id": two["id"], "quantity": 1}])).json()
    voided = buy(client, csrf, two).json()
    assert write(client, csrf, f"/api/sales/{voided['id']}/void", {"reason": "Error de prueba"}).status_code == 200
    write(client, csrf, f"/api/products/{one['id']}", {"name": "Nuevo", "price_cents": 999, "is_active": False}, "patch")
    report = client.get('/api/reports/summary').json()
    assert report['current'] == {"revenue_cents": "252", "sales": "1", "units": "3", "average_cents": "252"}
    assert report['top_units'][0]['name'] == sale['items'][0]['product_name_snapshot']
    assert report['top_units'][0]['units'] == '2'
    assert report['top_revenue'][0]['revenue_cents'] == '202'
    assert sum(int(h['sales']) for h in report['hours']) == 1
    assert sum(int(h['revenue_cents']) for h in report['hours']) == 252
    assert len(report['peak_hours']) == 1
    assert report['comparison']['revenue_cents']['percent_bp'] is None


def test_empty_and_comparison_zero(admin):
    client, _ = admin
    r = client.get('/api/reports/summary').json()
    assert set(r['current'].values()) == {'0'}
    assert r['top_units'] == r['top_revenue'] == r['peak_hours'] == []
    assert len(r['hours']) == 24
    assert all(c == {'delta': '0', 'percent_bp': '0'} for c in r['comparison'].values())


def test_day_year_boundaries_previous_cutoff_and_rounding(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    # Current Jan 1 00:00..12:00 BA; previous Dec 31 same elapsed interval.
    fixed(client)
    for stamp, cents in [('2026-01-01T02:59:59+00:00', 999),
                         ('2026-01-01T03:00:00+00:00', 100),
                         ('2026-01-01T14:59:59+00:00', 101),
                         ('2026-01-01T15:00:00+00:00', 777),
                         ('2025-12-31T03:00:00+00:00', 50),
                         ('2025-12-31T15:00:00+00:00', 555)]:
        seed(database, product['id'], stamp, cents)
    r = client.get('/api/reports/summary').json()
    assert r['current'] == {'revenue_cents': '201', 'sales': '2', 'units': '2', 'average_cents': '101'}
    assert r['previous']['revenue_cents'] == '50'
    assert r['comparison']['average_cents'] == {'delta': '51', 'percent_bp': '10100'}
    assert r['comparison']['revenue_cents'] == {'delta': '151', 'percent_bp': '30200'}
    assert r['peak_hours'] == [0, 11]
    assert r['period']['start_utc'] == '2026-01-01T03:00:00+00:00'
    assert r['previous_period']['end_utc'] == '2025-12-31T15:00:00+00:00'


def test_exact_aggregates_beyond_sqlite_and_javascript_limits(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    fixed(client)
    # > SQLite int64 (1025 * (2^53-1)); zero-price units independently exceed int64.
    for _ in range(1025):
        seed(database, product['id'], '2026-01-01T04:00:00+00:00', MAX_INTEGER)
        seed(database, product['id'], '2026-01-01T05:00:00+00:00', 0, MAX_INTEGER)
    r = client.get('/api/reports/summary')
    assert r.status_code == 200
    data = r.json()
    total = 1025 * MAX_INTEGER
    assert total > 2**63 - 1
    with sqlite3.connect(database) as db, pytest.raises(sqlite3.OperationalError, match='integer overflow'):
        db.execute('SELECT SUM(total_cents) FROM sales').fetchone()
    assert data['current']['revenue_cents'] == str(total)
    assert data['current']['units'] == str(total + 1025)
    assert data['top_units'][0]['units'] == str(total + 1025)
    assert data['hours'][1]['revenue_cents'] == str(total)
    assert data['hours'][2]['sales'] == '1025'


def test_employee_disabled_history_and_permissions(admin, database):
    client, csrf = admin
    employee = write(client, csrf, '/api/employees', {'username': 'worker', 'password': PASSWORD}).json()
    product = stock_product(client, csrf)
    fixed(client)
    seed(database, product['id'], '2026-01-01T04:00:00+00:00', user=employee['id'])
    login(client, 'worker')
    assert client.get('/api/reports/summary').status_code == 403
    csrf = login(client)
    write(client, csrf, f"/api/employees/{employee['id']}", {'is_active': False}, 'patch')
    assert client.get('/api/reports/summary').json()['current']['sales'] == '1'
    client.cookies.clear()
    assert client.get('/api/reports/summary').status_code == 401


def test_consistent_snapshot_when_void_commits_between_queries(admin, monkeypatch):
    client, csrf = admin
    product = stock_product(client, csrf)
    sale = buy(client, csrf, product).json()
    original = ReportingTransaction.metrics
    called = False
    def metrics(tx, interval):
        nonlocal called
        result = original(tx, interval)
        if not called:
            called = True
            assert write(client, csrf, f"/api/sales/{sale['id']}/void", {'reason': 'Prueba concurrente'}).status_code == 200
        return result
    monkeypatch.setattr(ReportingTransaction, 'metrics', metrics)
    r = client.get('/api/reports/summary').json()
    assert r['current']['sales'] == '1'
    assert r['top_units'][0]['units'] == '1'
    assert sum(int(h['sales']) for h in r['hours']) == 1
    assert client.get('/api/reports/summary').json()['current']['sales'] == '0'


@pytest.mark.parametrize('query', ['period=bad', 'period=custom', 'period=custom&start=2026-01-02&end=2026-01-01', 'period=custom&start=2024-01-01&end=2026-01-01', 'period=custom&start=2026-01-01&end=2099-01-01', 'period=today&start=2026-01-01', 'period=custom&start=bad&end=bad'])
def test_invalid_ranges(admin, query):
    client, _ = admin
    assert client.get('/api/reports/summary?' + query).status_code == 422


@pytest.mark.parametrize('period,days', [('today', 1), ('yesterday', 1), ('7d', 7), ('30d', 30)])
def test_presets_and_comparable_intervals(period, days):
    now = datetime(2026, 3, 1, 15, 30, tzinfo=UTC)
    current, old = periods(period, now, None, None)
    assert (current.start - old.start).days == days
    assert (current.end - old.end).days == days
    assert current.end - current.start == old.end - old.start
    if period == 'yesterday':
        assert current.end.hour == 0
    else:
        assert current.end.hour == 12


def test_custom_leap_month_and_zero_base_decline():
    current, previous = periods('custom', datetime(2024, 3, 2, tzinfo=UTC), date(2024, 2, 28), date(2024, 2, 29))
    assert current.end.day == 1 and current.end.month == 3
    assert (current.start - previous.start).days == 2
    assert rounded(1, 2) == 1 and rounded(-1, 2) == -1
    assert comparison(0, 1, 7, 1) == {'delta': '-7', 'percent_bp': '-10000'}
    assert comparison(1, 1, 0, 1)['percent_bp'] is None
    assert comparison(0, 1, 0, 1)['percent_bp'] == '0'
    with pytest.raises(IdentityError):
        periods('custom', datetime(2026, 1, 1, tzinfo=UTC), date(1999, 1, 1), date(1999, 1, 2))


def test_rank_limit_order_and_latest_snapshot(admin, database):
    client, csrf = admin
    fixed(client)
    for i in range(12):
        p = stock_product(client, csrf)
        seed(database, p['id'], '2026-01-01T04:00:00+00:00', price=i+1, quantity=12-i, name='Antes')
        seed(database, p['id'], '2026-01-01T05:00:00+00:00', price=0, name='Último')
    r = client.get('/api/reports/summary').json()
    assert len(r['top_units']) == len(r['top_revenue']) == 10
    assert r['top_units'][0]['units'] == '13'
    assert r['top_revenue'][0]['revenue_cents'] == '42'
    assert all(p['name'] == 'Último' for p in r['top_units'])
    assert r['top_revenue'][0]['product_id'] < r['top_revenue'][1]['product_id']


def test_peak_is_transactions_not_revenue_and_empty_current_declines(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf)
    fixed(client)
    seed(database, product['id'], '2026-01-01T04:00:00+00:00', price=10000)
    seed(database, product['id'], '2026-01-01T05:00:00+00:00', price=1)
    seed(database, product['id'], '2026-01-01T05:01:00+00:00', price=1)
    r = client.get('/api/reports/summary').json()
    assert r['peak_hours'] == [2]
    assert r['hours'][1]['revenue_cents'] == '10000'
    fixed(client, '2026-01-02T15:00:00+00:00')
    r = client.get('/api/reports/summary').json()
    assert r['current']['sales'] == '0' and r['previous']['sales'] == '3'
    assert r['comparison']['revenue_cents']['percent_bp'] == '-10000'
