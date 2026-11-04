"""
庫存回報 API 端點測試
測試 POST /api/inventory/report 的登入要求與回報者身分來源
"""

import pytest

from app.model.retailer import Retailer
from app.model.user import InventoryReport, User
from app.service.auth_service import create_jwt


@pytest.fixture
def retailer(db_session):
    store = Retailer(name="測試彩券行", city="台北市", lat=25.0330, lng=121.5654)
    db_session.add(store)
    db_session.commit()
    return store


@pytest.fixture
def reporter(db_session):
    user = User(lineUserId="U_reporter", displayName="回報者")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def other_user(db_session):
    user = User(lineUserId="U_other", displayName="被冒名者")
    db_session.add(user)
    db_session.commit()
    return user


class TestReportInventory:
    """POST /api/inventory/report"""

    def test_requires_login(self, client, db_session, retailer, other_user):
        """未帶 Token 應回傳 401，即使 body 帶了 userId"""
        payload = {
            "retailerId": retailer.id,
            "userId": other_user.id,
            "item": "200元",
            "status": "充足",
        }
        resp = client.post("/api/inventory/report", json=payload)
        assert resp.status_code == 401
        assert db_session.query(InventoryReport).count() == 0
        db_session.refresh(other_user)
        assert other_user.karmaPoints == 0

    def test_reporter_comes_from_token(self, client, db_session, retailer, reporter, other_user):
        """body 帶別人的 userId 會被忽略，回報與 Karma 都記在 Token 使用者身上"""
        payload = {
            "retailerId": retailer.id,
            "userId": other_user.id,
            "item": "200元",
            "status": "少量",
            "lat": 25.0330,
            "lng": 121.5654,
        }
        headers = {"Authorization": f"Bearer {create_jwt(reporter.id)}"}
        resp = client.post("/api/inventory/report", json=payload, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["userId"] == reporter.id

        report = db_session.query(InventoryReport).one()
        assert report.userId == reporter.id

        db_session.refresh(reporter)
        db_session.refresh(other_user)
        assert reporter.karmaPoints == 10
        assert other_user.karmaPoints == 0

    def test_banned_user_rejected(self, client, db_session, retailer, reporter):
        """被封禁的使用者回傳 403"""
        reporter.isBanned = 1
        db_session.commit()
        payload = {"retailerId": retailer.id, "item": "200元", "status": "完售"}
        headers = {"Authorization": f"Bearer {create_jwt(reporter.id)}"}
        resp = client.post("/api/inventory/report", json=payload, headers=headers)
        assert resp.status_code == 403
        assert db_session.query(InventoryReport).count() == 0
