"""
中獎打卡 API 端點測試
測試 GET /api/map/checkins、POST /api/map/checkin
"""

import pytest

from app.model.database import Checkin
from app.model.retailer import Retailer
from app.model.user import KarmaLog, User
from app.service.auth_service import create_jwt


@pytest.fixture
def auth_headers(db_session):
    """建立測試使用者並回傳帶 Bearer Token 的 headers"""
    user = User(lineUserId="U_checkin_tester", displayName="打卡測試")
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_jwt(user.id)}"}


class TestCheckinList:
    """GET /api/map/checkins"""

    def test_empty_checkins(self, client):
        """無打卡紀錄時回傳空陣列"""
        resp = client.get("/api/map/checkins")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_checkins(self, client, db_session):
        """有資料時回傳打卡列表"""
        checkin = Checkin(city="台北市", amount=10000, gameName="刮刮樂A")
        db_session.add(checkin)
        db_session.commit()

        resp = client.get("/api/map/checkins")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["city"] == "台北市"
        assert data[0]["amount"] == 10000


class TestCreateCheckin:
    """POST /api/map/checkin"""

    def test_create_checkin(self, client, auth_headers):
        """成功新增一筆打卡"""
        payload = {"city": "新北市", "amount": 50000, "gameName": "金運旺"}
        resp = client.post("/api/map/checkin", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["city"] == "新北市"
        assert data["amount"] == 50000
        assert data["gameName"] == "金運旺"
        assert "id" in data

    def test_create_checkin_without_game_name(self, client, auth_headers):
        """不帶款式名稱也能成功"""
        payload = {"city": "台中市", "amount": 1000}
        resp = client.post("/api/map/checkin", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["gameName"] == ""

    def test_create_checkin_missing_required_field(self, client, auth_headers):
        """缺少必填欄位應回傳 422"""
        payload = {"amount": 1000}
        resp = client.post("/api/map/checkin", json=payload, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_checkin_with_retailer(self, client, db_session, auth_headers):
        """帶店家 ID 會寫入 checkin 並回傳"""
        store = Retailer(name="打卡測試店", city="台北市")
        db_session.add(store)
        db_session.commit()
        payload = {"city": "台北市", "amount": 2000, "retailerId": store.id}
        resp = client.post("/api/map/checkin", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["retailerId"] == store.id
        assert db_session.query(Checkin).one().retailerId == store.id

    def test_create_checkin_unknown_retailer(self, client, db_session, auth_headers):
        """店家不存在回 404，且不寫入"""
        payload = {"city": "台北市", "amount": 2000, "retailerId": 999999}
        resp = client.post("/api/map/checkin", json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert db_session.query(Checkin).count() == 0

    def test_checkin_karma_daily_limit(self, client, db_session, auth_headers):
        """每次 +5，每天最多給分 3 次"""
        for _ in range(4):
            resp = client.post("/api/map/checkin", json={"city": "台中市", "amount": 100}, headers=auth_headers)
            assert resp.status_code == 201
        user = db_session.query(User).filter(User.lineUserId == "U_checkin_tester").one()
        db_session.refresh(user)
        assert user.karmaPoints == 15
        assert db_session.query(KarmaLog).filter(KarmaLog.action == "checkin").count() == 3

    def test_create_checkin_requires_login(self, client, db_session):
        """未帶 Token 應回傳 401，且不寫入資料"""
        payload = {"city": "台南市", "amount": 2000}
        resp = client.post("/api/map/checkin", json=payload)
        assert resp.status_code == 401
        assert db_session.query(Checkin).count() == 0
