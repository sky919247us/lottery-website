"""
刮刮樂 API 端點測試
測試 GET /api/scratchcards、GET /api/scratchcards/{id}
"""

from app.model.database import Scratchcard, PrizeStructure


def _seed_scratchcard(db, **overrides):
    """建立測試用刮刮樂資料"""
    defaults = {
        "gameId": "TEST001",
        "name": "測試刮刮樂",
        "price": 200,
        "maxPrize": "100萬元",
        "maxPrizeAmount": 1000000,
        "totalIssued": 1000000,
        "salesRate": "50%",
        "salesRateValue": 50.0,
        "grandPrizeCount": 5,
        "grandPrizeUnclaimed": 3,
        "isHighWinRate": False,
        "issueDate": "114/01/01",
        "overallWinRate": "69.33%",
    }
    defaults.update(overrides)
    card = Scratchcard(**defaults)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _seed_prize(db, scratchcard_id, prize_name="頭獎", amount=1000000, count=5):
    """建立測試用獎金結構"""
    prize = PrizeStructure(
        scratchcardId=scratchcard_id,
        prizeName=prize_name,
        prizeAmount=amount,
        totalCount=count,
    )
    db.add(prize)
    db.commit()
    return prize


class TestScratchcardList:
    """GET /api/scratchcards 列表端點"""

    def test_empty_list(self, client):
        """資料庫為空時應回傳空陣列"""
        resp = client.get("/api/scratchcards")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_items(self, client, db_session):
        """有資料時應回傳列表"""
        _seed_scratchcard(db_session)
        resp = client.get("/api/scratchcards")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["gameId"] == "TEST001"
        assert data[0]["name"] == "測試刮刮樂"

    def test_filter_by_price(self, client, db_session):
        """依售價篩選"""
        _seed_scratchcard(db_session, gameId="G200", price=200)
        _seed_scratchcard(db_session, gameId="G500", name="高價款", price=500)
        resp = client.get("/api/scratchcards?price=500")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["price"] == 500

    def test_filter_high_win_only(self, client, db_session):
        """僅顯示高勝率款式"""
        _seed_scratchcard(db_session, gameId="G1", isHighWinRate=False)
        _seed_scratchcard(db_session, gameId="G2", name="高勝率款", isHighWinRate=True)
        resp = client.get("/api/scratchcards?high_win_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["isHighWinRate"] is True

    def test_sort_by_price_desc(self, client, db_session):
        """依價格降序排列"""
        _seed_scratchcard(db_session, gameId="G100", price=100)
        _seed_scratchcard(db_session, gameId="G500", name="高價", price=500)
        resp = client.get("/api/scratchcards?sort_by=price&order=desc")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["price"] >= data[-1]["price"]


class TestScratchcardDetail:
    """GET /api/scratchcards/{id} 詳情端點"""

    def test_detail_found(self, client, db_session):
        """查詢存在的刮刮樂應回傳詳情"""
        card = _seed_scratchcard(db_session)
        _seed_prize(db_session, card.id, "頭獎", 1000000, 5)
        _seed_prize(db_session, card.id, "貳獎", 100000, 20)

        resp = client.get(f"/api/scratchcards/{card.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gameId"] == "TEST001"
        assert len(data["prizes"]) == 2

    def test_detail_not_found(self, client):
        """查詢不存在的 ID 應回傳 404"""
        resp = client.get("/api/scratchcards/99999")
        assert resp.status_code == 404

    def test_detail_includes_prize_structure(self, client, db_session):
        """確認獎金結構欄位完整"""
        card = _seed_scratchcard(db_session)
        _seed_prize(db_session, card.id, "頭獎", 2000000, 3)

        resp = client.get(f"/api/scratchcards/{card.id}")
        data = resp.json()
        prize = data["prizes"][0]
        assert prize["prizeName"] == "頭獎"
        assert prize["prizeAmount"] == 2000000
        assert prize["totalCount"] == 3
