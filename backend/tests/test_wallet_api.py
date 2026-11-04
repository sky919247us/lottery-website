"""
錢包紀錄 API 端點測試
測試 POST /api/wallet/records 的店家綁定與同步到熱區
"""

import pytest

from app.model.database import Checkin
from app.model.pnl_record import PnLRecord
from app.model.retailer import Retailer
from app.model.user import User
from app.service.auth_service import create_jwt


@pytest.fixture
def auth_headers(db_session):
    user = User(lineUserId="U_wallet_tester", displayName="錢包測試")
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_jwt(user.id)}"}


@pytest.fixture
def retailer(db_session):
    store = Retailer(name="錢包測試店", city="高雄市")
    db_session.add(store)
    db_session.commit()
    return store


class TestCreateWalletRecord:
    """POST /api/wallet/records"""

    def test_shared_record_syncs_retailer_to_checkin(self, client, db_session, auth_headers, retailer):
        """公開分享的中獎紀錄，店家 ID 會一起寫進熱區 checkin"""
        payload = {
            "gameName": "金運旺", "spent": 200, "won": 1000,
            "city": "高雄市", "sharedToPublic": True, "retailerId": retailer.id,
        }
        resp = client.post("/api/wallet/records", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["retailerId"] == retailer.id
        assert db_session.query(PnLRecord).one().retailerId == retailer.id
        assert db_session.query(Checkin).one().retailerId == retailer.id

    def test_unknown_retailer_rejected(self, client, db_session, auth_headers):
        """店家不存在回 404，且不寫入任何紀錄"""
        payload = {"spent": 200, "won": 0, "retailerId": 999999}
        resp = client.post("/api/wallet/records", json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert db_session.query(PnLRecord).count() == 0

    def test_record_without_retailer(self, client, db_session, auth_headers):
        """不選店家也能記帳"""
        resp = client.post("/api/wallet/records", json={"spent": 300, "won": 0}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["retailerId"] is None
