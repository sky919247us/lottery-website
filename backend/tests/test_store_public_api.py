"""
店家公開頁 API 與頭獎綁店家測試
測試 GET /api/stores/{id}/public、GET /api/stores/indexable、
scraper_service 回寫 JackpotStore.retailerId
"""

from datetime import datetime, timedelta

import pytest

from app.model.database import Checkin
from app.model.jackpot_store import JackpotStore
from app.model.rating import RetailerRating
from app.model.retailer import Retailer
from app.model.user import User
from app.service.scraper_service import _update_retailer_jackpot_counts


@pytest.fixture
def store(db_session):
    s = Retailer(name="好運彩券行", address="台北市中正區重慶南路一段10號", city="台北市", district="中正區")
    db_session.add(s)
    db_session.commit()
    return s


class TestJackpotLinking:
    """_update_retailer_jackpot_counts 回寫 retailerId"""

    def test_links_matched_and_clears_unmatched(self, db_session, store):
        matched = JackpotStore(gameType="今彩539", period="115000001", drawDate="2026/01/02",
                               storeName="好運彩券行", storeAddress="台北市中正區重慶南路一段10號")
        unmatched = JackpotStore(gameType="大樂透", period="115000002", drawDate="2026/01/03",
                                 storeName="不存在的店", storeAddress="高雄市前鎮區某某路99號",
                                 retailerId=store.id)  # 舊的錯誤綁定要被清掉
        db_session.add_all([matched, unmatched])
        db_session.commit()

        _update_retailer_jackpot_counts()

        db_session.expire_all()
        assert db_session.get(JackpotStore, matched.id).retailerId == store.id
        assert db_session.get(JackpotStore, unmatched.id).retailerId is None
        assert db_session.get(Retailer, store.id).jackpotCount == 1

    def test_address_only_match_not_linked(self, db_session, store):
        """只靠地址對到（店名不同）不綁 retailerId，但 jackpotCount 照原邏輯計入"""
        jp = JackpotStore(gameType="威力彩", period="115000003", drawDate="2026/01/04",
                          storeName="別家彩券行", storeAddress="台北市中正區重慶南路一段10號",
                          retailerId=store.id)  # 舊綁定要被清掉
        db_session.add(jp)
        db_session.commit()

        _update_retailer_jackpot_counts()

        db_session.expire_all()
        assert db_session.get(JackpotStore, jp.id).retailerId is None
        assert db_session.get(Retailer, store.id).jackpotCount == 1


class TestStorePublic:
    """GET /api/stores/{id}/public"""

    def test_not_found(self, client):
        resp = client.get("/api/stores/999999/public")
        assert resp.status_code == 404

    def test_sections(self, client, db_session, store):
        user = User(lineUserId="U_rater", displayName="評分者", karmaLevel=3)
        db_session.add(user)
        db_session.commit()
        db_session.add_all([
            JackpotStore(gameType="今彩539", period="115000001", drawDate="2026/01/02",
                         storeName="好運彩券行", storeAddress="x", retailerId=store.id),
            RetailerRating(userId=user.id, retailerId=store.id, rating=5,
                           serviceTags="店員親切", comment="老闆很好", karmaWeight=1.0),
            Checkin(city="台北市", amount=2000, gameName="金運旺", retailerId=store.id),
            Checkin(city="台北市", amount=500, gameName="", retailerId=store.id,
                    createdAt=datetime.utcnow() - timedelta(days=200)),  # 超過 90 天不算
        ])
        db_session.commit()

        resp = client.get(f"/api/stores/{store.id}/public")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "好運彩券行"
        assert data["isPro"] is False
        assert data["jackpots"]["count"] == 1
        assert data["jackpots"]["items"][0]["gameType"] == "今彩539"
        assert data["ratings"]["totalCount"] == 1
        assert data["ratings"]["avgRating"] == 5.0
        review = data["ratings"]["recent"][0]
        assert review["comment"] == "老闆很好"
        assert review["userName"] == "評分者"
        assert "userId" not in review
        assert data["winReports"]["count"] == 1
        assert data["winReports"]["totalAmount"] == 2000
        assert data["inventory"] == {"official": [], "community": []}

    def test_empty_store(self, client, store):
        data = client.get(f"/api/stores/{store.id}/public").json()
        assert data["jackpots"]["count"] == 0
        assert data["ratings"]["totalCount"] == 0
        assert data["winReports"]["count"] == 0


class TestIndexable:
    """GET /api/stores/indexable"""

    def test_threshold(self, client, db_session):
        jackpot_store = Retailer(name="頭獎店")
        rated_store = Retailer(name="有評分")
        busy_store = Retailer(name="三則回報")
        quiet_store = Retailer(name="兩則回報")
        empty_store = Retailer(name="空店")
        db_session.add_all([jackpot_store, rated_store, busy_store, quiet_store, empty_store])
        db_session.commit()
        user = User(lineUserId="U_idx")
        db_session.add(user)
        db_session.commit()
        db_session.add_all([
            JackpotStore(gameType="威力彩", period="1", storeName="頭獎店", retailerId=jackpot_store.id),
            RetailerRating(userId=user.id, retailerId=rated_store.id, rating=4),
            *[Checkin(city="台北市", amount=100, retailerId=busy_store.id) for _ in range(3)],
            *[Checkin(city="台北市", amount=100, retailerId=quiet_store.id) for _ in range(2)],
        ])
        db_session.commit()

        resp = client.get("/api/stores/indexable")
        assert resp.status_code == 200
        ids = {row["id"] for row in resp.json()}
        assert ids == {jackpot_store.id, rated_store.id, busy_store.id}
        assert all(row["lastmod"] for row in resp.json())
