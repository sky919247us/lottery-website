"""
使用 TGOS 全國門牌地址定位服務 API 批次 geocoding
端點：https://addr.tgos.tw/addrws/v30/QueryAddr.asmx/QueryAddr
回傳座標系統：EPSG:4326 (WGS84 經緯度)
每日上限：10,000 筆（一般使用）/ 30 萬筆/月（進階使用）
"""

import json
import logging
import sys
import time
from pathlib import Path

import requests

# 確保能匯入 app.model
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import SessionLocal, init_db
from app.model.retailer import Retailer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --- TGOS API 設定 ---
TGOS_ENDPOINT = "https://addr.tgos.tw/addrws/v30/QueryAddr.asmx/QueryAddr"
TGOS_APPID = "OV1r3C1HBWsczWvLmrqLkaEYnVJpy/zjuWrWzYOy+6gpZGF1BmnXkQ=="
TGOS_APIKEY = (
    "aeyf21l4lyZuZNwIzttyFOxzRxLynVdT8cg5Qe8dCLx8aJhvrFwjkjy4Y71ipompJf35zkHzb+A"
    "kao/QTUiYLowmBWM0FD5/zZkW4oDbaCxMIB1WYf00QOmxeH+qxjRtD/NKOanotlUt+QCZz3YYt/"
    "VAH80JoRbAuUDmdCzwmrNdyxZBwG8g0EH1VVZhlZOWq7nFMET8OPVfkvkHGlJ9S3RXjtIfRT7nVy"
    "2tRS7Z0U+fcIgFHVNhlpKm16S214djdoOswLUW3SJh22BoI69Hcyyp7ruQcVhM7+k3U9bKlepUPq"
    "qg3Brvgr+ioJGP41ZzhDUXQjAySVS/iIsJWPRt5HJ00UMrHD9oPwksBjEJ7y7dejB5lv/a2W5SHw"
    "Zb+6tA2Qj9ZufV8I+TBDJ5h/6xaiiM0zifUMNxH7ZaTh3eM3c="
)


def query_tgos(address: str) -> tuple[float | None, float | None]:
    """
    呼叫 TGOS 即時地址定位 API，回傳 (lat, lng) 或 (None, None)
    座標系統：WGS84 (EPSG:4326)
    """
    params = {
        "oAPPId": TGOS_APPID,
        "oAPIKey": TGOS_APIKEY,
        "oAddress": address,
        "oSRS": "EPSG:4326",
        "oFuzzyType": "2",       # 模糊比對等級 2（允許最寬鬆比對）
        "oResultDataType": "JSON",
        "oFuzzyBuffer": "0",
        "oIsOnlyFullMatch": "false",
        "oIsSupportPast": "true",
        "oIsShowCodeBase": "false",
        "oIsLockCounty": "true",
        "oIsLockTown": "false",
        "oIsLockVillage": "false",
        "oIsLockRoadSection": "false",
        "oIsLockLane": "false",
        "oIsLockAlley": "false",
        "oIsLockArea": "false",
        "oIsSameNumber_SubNumber": "true",
        "oCanIgnoreVillage": "true",
        "oCanIgnoreNeighborhood": "true",
        "oReturnMaxCount": "1",
    }

    try:
        resp = requests.get(TGOS_ENDPOINT, params=params, timeout=15)
        resp.raise_for_status()

        # TGOS 回傳的是 XML 包裹的 JSON 字串，需要解析
        # 回傳格式可能是純 JSON 或 XML 包裹，嘗試兩種
        text = resp.text.strip()

        # 嘗試直接 JSON 解析
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 可能是 XML 包裹 <string>...</string>
            import re
            json_match = re.search(r'<string[^>]*>(.*?)</string>', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # 嘗試去除 XML 頭部直接取 JSON
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    logger.warning(f"  無法解析 TGOS 回應: {text[:200]}")
                    return None, None

        # 解析座標
        # TGOS V3 回傳格式：
        # {"Info":{"MatchType":"...","MatchAddr":"..."},"AddressList":[{"X":121.xxx,"Y":25.xxx,...}]}
        if isinstance(data, dict):
            addr_list = data.get("AddressList") or data.get("addressList") or []
            if addr_list and len(addr_list) > 0:
                item = addr_list[0]
                x = item.get("X") or item.get("x")
                y = item.get("Y") or item.get("y")
                if x is not None and y is not None:
                    # EPSG:4326 → X = 經度(lng), Y = 緯度(lat)
                    return float(y), float(x)

        return None, None

    except requests.RequestException as e:
        logger.warning(f"  TGOS API 請求失敗: {e}")
        return None, None
    except Exception as e:
        logger.warning(f"  TGOS 解析異常: {e}")
        return None, None


def geocode_all(batch_size: int = 0, delay: float = 0.15):
    """
    批次 geocoding 所有缺少座標的經銷商
    Args:
        batch_size: 限制處理筆數，0 表示全部
        delay: 每筆之間的延遲秒數（避免被封鎖）
    """
    init_db()
    db = SessionLocal()
    failed_log = Path(__file__).parent / "tgos_geocode_failed.txt"

    try:
        # 查詢所有缺少座標的經銷商
        retailers = db.query(Retailer).filter(Retailer.lat.is_(None)).all()
        total = len(retailers)

        if batch_size > 0:
            retailers = retailers[:batch_size]

        process_count = len(retailers)
        logger.info(f"🚀 開始 TGOS Geocoding：{process_count} / {total} 筆待處理")

        success = 0
        failed = 0
        failed_list: list[str] = []

        for i, r in enumerate(retailers):
            # 組合完整地址
            full_addr = f"{r.city or ''}{r.district or ''}{r.address or ''}"
            if not full_addr.strip():
                failed += 1
                failed_list.append(f"{r.id}|{r.name}|（空地址）")
                continue

            lat, lng = query_tgos(full_addr)

            if lat is not None and lng is not None:
                r.lat = lat
                r.lng = lng
                success += 1
            else:
                # 嘗試只用原始 address 欄位（可能本身就包含完整地址）
                if r.address and r.address != full_addr:
                    lat2, lng2 = query_tgos(r.address)
                    if lat2 is not None and lng2 is not None:
                        r.lat = lat2
                        r.lng = lng2
                        success += 1
                    else:
                        failed += 1
                        failed_list.append(f"{r.id}|{r.name}|{full_addr}")
                else:
                    failed += 1
                    failed_list.append(f"{r.id}|{r.name}|{full_addr}")

            # 每 100 筆 commit + 進度報告
            if (i + 1) % 100 == 0:
                db.commit()
                pct = (i + 1) / process_count * 100
                logger.info(
                    f"  📊 進度 {i + 1}/{process_count} ({pct:.1f}%) "
                    f"| ✅ 成功 {success} | ❌ 失敗 {failed}"
                )

            # 延遲避免過快
            time.sleep(delay)

        # 最後一次 commit
        db.commit()

        # 寫入失敗紀錄
        if failed_list:
            with open(failed_log, "w", encoding="utf-8") as f:
                f.write("\n".join(failed_list))
            logger.info(f"📝 失敗紀錄已寫入 {failed_log}")

        logger.info(
            f"🎉 TGOS Geocoding 完成！"
            f"✅ 成功 {success} | ❌ 失敗 {failed} | 📦 總計 {process_count}"
        )

        return success, failed

    except Exception as e:
        logger.error(f"❌ Geocoding 失敗: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TGOS 全國門牌地址定位 Geocoding")
    parser.add_argument("--batch", type=int, default=0, help="限制處理筆數（0=全部）")
    parser.add_argument("--delay", type=float, default=0.15, help="每筆延遲秒數")
    args = parser.parse_args()

    geocode_all(batch_size=args.batch, delay=args.delay)
