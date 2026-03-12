"""
中獎打卡 API 端點測試
測試 GET /api/map/checkins、POST /api/map/checkin
"""

from app.model.database import Checkin


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

    def test_create_checkin(self, client):
        """成功新增一筆打卡"""
        payload = {"city": "新北市", "amount": 50000, "gameName": "金運旺"}
        resp = client.post("/api/map/checkin", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["city"] == "新北市"
        assert data["amount"] == 50000
        assert data["gameName"] == "金運旺"
        assert "id" in data

    def test_create_checkin_without_game_name(self, client):
        """不帶款式名稱也能成功"""
        payload = {"city": "台中市", "amount": 1000}
        resp = client.post("/api/map/checkin", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["gameName"] == ""

    def test_create_checkin_missing_required_field(self, client):
        """缺少必填欄位應回傳 422"""
        payload = {"amount": 1000}
        resp = client.post("/api/map/checkin", json=payload)
        assert resp.status_code == 422
