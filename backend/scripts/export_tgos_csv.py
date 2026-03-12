"""
匯出經銷商地址為 TGOS 批次比對 CSV 格式
TGOS 範本格式：id,Address,Response_Address,Response_X,Response_Y
每日上限 10,000 筆
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import SessionLocal, init_db
from app.model.retailer import Retailer


def export_csv(all_retailers: bool = False):
    """
    匯出經銷商地址為 TGOS CSV
    Args:
        all_retailers: 是否匯出所有店家（True=全量, False=僅缺失座標者）
    """
    init_db()
    db = SessionLocal()

    try:
        if all_retailers:
            retailers = db.query(Retailer).all()
            prefix_msg = "全量"
        else:
            retailers = db.query(Retailer).filter(Retailer.lat.is_(None)).all()
            prefix_msg = "待補齊"
            
        total = len(retailers)
        print(f"共 {total} 筆{prefix_msg}資料待處理")

        output_dir = Path(__file__).resolve().parent
        batch_size = 10000
        file_index = 1

        for start in range(0, total, batch_size):
            batch = retailers[start:start + batch_size]
            suffix = "_all" if all_retailers else ""
            filename = output_dir / f"tgos_batch{suffix}_{file_index}.csv"

            with open(filename, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "Address", "Response_Address", "Response_X", "Response_Y"])

                for r in batch:
                    city = r.city or ""
                    district = r.district or ""
                    addr = r.address or ""
                    
                    # 組合地址
                    prefix = f"{city}{district}"
                    if prefix and addr.startswith(prefix):
                        full_addr = addr
                    elif city and addr.startswith(city):
                        full_addr = addr
                    else:
                        full_addr = f"{prefix}{addr}"

                    # --- 強力清理邏輯 ---
                    import re
                    # 1. 移除括號及其內容（例如：(農會旁)、(臨)）
                    cleaned = re.sub(r'\(.*?\)', '', full_addr)
                    # 2. 移除全角括號
                    cleaned = re.sub(r'（.*?）', '', cleaned)
                    # 3. 移除樓層資訊（2樓、二樓、3F等）
                    cleaned = re.sub(r'\d+樓.*$', '', cleaned)
                    cleaned = re.sub(r'[一二三四五六七八九十]+樓.*$', '', cleaned)
                    cleaned = re.sub(r'\d+F.*$', '', cleaned, flags=re.IGNORECASE)
                    # 4. 移除鄰、里、村資訊（TGOS 有時會因為這些資訊誤差）
                    cleaned = re.sub(r'\d+鄰', '', cleaned)
                    cleaned = re.sub(r'.*?[里村]', '', cleaned, count=1) if len(cleaned) > 10 else cleaned
                    # 5. 移除尾部多餘符號
                    cleaned = re.sub(r'[、，,(\s]+$', '', cleaned)
                    
                    # 確保地址至少有縣市區域
                    if len(cleaned.strip()) < 5:
                        cleaned = full_addr

                    writer.writerow([r.id, cleaned.strip(), "", "", ""])

            print(f"✅ 已產出 {filename.name}（{len(batch)} 筆）")
            file_index += 1

        print(f"\n🎉 共產出 {file_index - 1} 個 CSV 檔案")
        print("請至 https://www.tgos.tw/TGOS/Addr/addrCompare 上傳比對")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="匯出 TGOS 批次比對 CSV")
    parser.add_argument("--all", action="store_true", help="是否全量匯出")
    args = parser.parse_args()
    
    export_csv(all_retailers=args.all)
