"""大樣本統計（整本開箱）API 測試

重點在資料分級：未登入與一般會員都不該拿到逐張序號。
"""
import pytest

from app.api.cache import clear_cache
from app.model.database import PrizeStructure, Scratchcard
from app.model.unboxing import UnboxingBook, UnboxingSession
from app.model.user import User
from app.service.auth_service import create_jwt


@pytest.fixture(autouse=True)
def _clear_cache():
    """/summary 與 /games 有 10 分鐘程序內快取，測試間必須清掉才不會互相污染"""
    clear_cache("unboxing:")
    yield
    clear_cache("unboxing:")


def _seed_card(db, game_id="5138", price=300, total_issued=1000000):
    card = Scratchcard(
        gameId=game_id,
        name="測試款",
        price=price,
        totalIssued=total_issued,
        imageUrl="",
        issueDate="115/03/10",
        endDate="115/09/10",
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    # 派彩率 60%：一張 $600 的獎，總共 1,000 張 → 600,000 / (1,000,000 * 300)
    db.add(
        PrizeStructure(
            scratchcardId=card.id,
            prizeName="NT$600",
            prizeAmount=600,
            totalCount=1000,
        )
    )
    db.commit()
    return card


def _seed_session(db, game_id="5138", price=300, books=2, tickets=10, prize=600):
    session = UnboxingSession(
        gameId=game_id,
        gameName="測試款",
        price=price,
        title="測試場次",
        sourceFile="test.csv",
        ticketsPerBook=tickets,
        bookCount=books,
        isPublished=True,
    )
    db.add(session)
    db.flush()
    for i in range(books):
        prizes = [0] * tickets
        prizes[i] = prize  # 每本中一張，位置不同
        db.add(
            UnboxingBook(
                session=session,
                gameId=game_id,
                serialNo="1000%d" % i,
                label="1000%d" % i,
                batchKey="批次A",
                seq=i + 1,
                ticketCount=tickets,
                prizes=prizes,
                totalPrize=prize,
                winCount=1,
            )
        )
    db.commit()
    return session


def _auth_header(db, karma_points=0, karma_level=1):
    user = User(
        lineUserId="U%d" % karma_points,
        displayName="測試員",
        karmaPoints=karma_points,
        karmaLevel=karma_level,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"Authorization": "Bearer %s" % create_jwt(user.id)}


class TestUnboxingSummary:
    """GET /api/unboxing/summary"""

    def test_empty(self, client):
        resp = client.get("/api/unboxing/summary")
        assert resp.status_code == 200
        assert resp.json()["bookCount"] == 0

    def test_totals(self, client, db_session):
        _seed_card(db_session)
        _seed_session(db_session)
        resp = client.get("/api/unboxing/summary")
        data = resp.json()
        assert data["bookCount"] == 2
        assert data["ticketCount"] == 20
        assert data["totalCost"] == 20 * 300
        assert data["totalPrize"] == 1200
        assert data["returnRate"] == pytest.approx(0.2)


class TestUnboxingGames:
    """GET /api/unboxing/games"""

    def test_sorted_by_game_id_desc(self, client, db_session):
        _seed_card(db_session, game_id="5100")
        _seed_card(db_session, game_id="5200")
        _seed_session(db_session, game_id="5100")
        _seed_session(db_session, game_id="5200")
        resp = client.get("/api/unboxing/games")
        ids = [g["gameId"] for g in resp.json()]
        assert ids == ["5200", "5100"]

    def test_official_return_rate(self, client, db_session):
        _seed_card(db_session)
        _seed_session(db_session)
        row = client.get("/api/unboxing/games").json()[0]
        assert row["officialReturnRate"] == pytest.approx(0.002)
        assert row["returnRate"] == pytest.approx(0.2)
        assert row["returnRateDelta"] == pytest.approx(0.198)
        assert row["batchCount"] == 1


class TestUnboxingDetailAccess:
    """GET /api/unboxing/games/{gameId} 的三層權限"""

    def test_404_when_missing(self, client):
        assert client.get("/api/unboxing/games/9999").status_code == 404

    def test_anonymous_gets_no_books(self, client, db_session):
        _seed_card(db_session)
        _seed_session(db_session)
        data = client.get("/api/unboxing/games/5138").json()
        assert data["accessLevel"] == 0
        assert data["books"] == []
        # 彙總統計仍要給
        assert data["measured"]["bookCount"] == 2
        assert len(data["measured"]["positionWins"]) == 10

    def test_logged_in_gets_masked_serial_without_prizes(self, client, db_session):
        _seed_card(db_session)
        _seed_session(db_session)
        headers = _auth_header(db_session, karma_points=100, karma_level=2)
        data = client.get("/api/unboxing/games/5138", headers=headers).json()
        assert data["accessLevel"] == 1
        assert len(data["books"]) == 2
        book = data["books"][0]
        assert book["label"] == "1***0"
        assert "serialNo" not in book
        assert "prizes" not in book
        assert book["missCount"] == 9

    def test_level5_gets_full_serial_and_prizes(self, client, db_session):
        _seed_card(db_session)
        _seed_session(db_session)
        headers = _auth_header(db_session, karma_points=1500, karma_level=5)
        data = client.get("/api/unboxing/games/5138", headers=headers).json()
        assert data["accessLevel"] == 2
        book = data["books"][0]
        assert book["serialNo"] == "10000"
        assert book["prizes"][0] == 600

    def test_stale_karma_level_still_unlocks_by_points(self, client, db_session):
        """karmaLevel 是快取欄位，積分已達標就該放行"""
        _seed_card(db_session)
        _seed_session(db_session)
        headers = _auth_header(db_session, karma_points=1500, karma_level=1)
        data = client.get("/api/unboxing/games/5138", headers=headers).json()
        assert data["accessLevel"] == 2

    def test_banned_user_treated_as_anonymous(self, client, db_session):
        _seed_card(db_session)
        _seed_session(db_session)
        user = User(
            lineUserId="Ubanned",
            displayName="封禁",
            karmaPoints=9999,
            karmaLevel=9,
            isBanned=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        headers = {"Authorization": "Bearer %s" % create_jwt(user.id)}
        data = client.get("/api/unboxing/games/5138", headers=headers).json()
        assert data["accessLevel"] == 0
        assert data["books"] == []

    def test_unpublished_session_not_exposed(self, client, db_session):
        _seed_card(db_session)
        session = _seed_session(db_session)
        session.isPublished = False
        db_session.commit()
        assert client.get("/api/unboxing/games/5138").status_code == 404
