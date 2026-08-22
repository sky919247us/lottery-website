"""
測試共用 fixtures
提供測試用 SQLite in-memory 資料庫、FastAPI TestClient
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.cache import clear_cache
from app.model.database import Base, get_db
from app.main import app


# 使用 in-memory SQLite 作為測試資料庫
TEST_DATABASE_URL = "sqlite:///./test_scratchcard.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _clear_api_cache():
    """清空 API 的程序內快取

    app/api/cache.py 是模組級 dict，TTL 最長 86400 秒。若不清，前一個測試的
    結果會被下一個測試讀到（例如 test_empty_list 把空陣列寫進去，
    test_returns_items 就永遠拿到空陣列）。快取是跨測試共用的全域狀態，
    因此放在 conftest 而非個別測試檔。
    """
    clear_cache()
    yield
    clear_cache()


@pytest.fixture(scope="function")
def db_session():
    """每個測試函式獨立的 DB Session，測試結束後自動回滾"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient，注入測試用 DB Session"""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
