"""
YT 影片研究列表: 兌獎截止日未到、上市 ≥ 6 個月、有銷售率的款式。

輸出兩份 CSV 與一份 Markdown 摘要:
  - research_groupA_still_jackpot.csv  → 頭獎還剩 (可衝一波), 依「現況返還率提升」排序
  - research_groupB_jackpot_gone.csv   → 頭獎已開光 (不推薦), 依距兌獎截止天數排序
  - research_summary.md                → 兩組合併摘要 (可直接貼到影片大綱)

執行: 在 backend/ 下 `python research_redeem_window.py`
"""
from __future__ import annotations
import csv
import os
import re
from datetime import date, timedelta

from app.model.database import PrizeStructure, Scratchcard, SessionLocal


# ── 設定 ──────────────────────────────────────────────────────
HALF_YEAR_DAYS = 180
TODAY = date.today()
HALF_YEAR_AGO = TODAY - timedelta(days=HALF_YEAR_DAYS)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def roc_to_date(s: str) -> date | None:
    """民國年字串轉 date. 支援 '114/05/01', '114-05-01', '114年5月1日'."""
    if not s:
        return None
    s = s.strip()
    m = re.match(r"(\d{2,3})\D+(\d{1,2})\D+(\d{1,2})", s)
    if not m:
        return None
    try:
        roc_y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(roc_y + 1911, mo, d)
    except ValueError:
        return None


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x * 100:.1f}%"


def big_prize_summary(prizes: list[PrizeStructure], top_n: int = 4) -> str:
    """列出前 N 大獎項 (依金額排序), 顯示金額 + 總張數."""
    sorted_p = sorted(
        [p for p in prizes if (p.prizeAmount or 0) > 0],
        key=lambda p: p.prizeAmount or 0,
        reverse=True,
    )
    chunks = []
    for p in sorted_p[:top_n]:
        amt = p.prizeAmount or 0
        cnt = p.totalCount or 0
        chunks.append(f"{amt:,}×{cnt}")
    return " / ".join(chunks)


def main() -> None:
    db = SessionLocal()
    try:
        cards = (
            db.query(Scratchcard)
            .filter(Scratchcard.isPreview == False)  # noqa: E712
            .filter(Scratchcard.salesRateValue > 0)
            .all()
        )

        group_a: list[dict] = []  # 還有頭獎
        group_b: list[dict] = []  # 頭獎已開光
        skipped = 0

        for c in cards:
            issue = roc_to_date(c.issueDate)
            redeem = roc_to_date(c.redeemDeadline)
            if not issue or not redeem:
                skipped += 1
                continue
            if redeem < TODAY:
                continue  # 已截止
            if issue > HALF_YEAR_AGO:
                continue  # 上市未滿半年

            prizes = (
                db.query(PrizeStructure)
                .filter(PrizeStructure.scratchcardId == c.id)
                .all()
            )
            total = c.totalIssued or 0
            price = c.price or 0
            sold_ratio = (c.salesRateValue or 0.0) / 100.0
            remaining_tickets = int(total * (1 - sold_ratio)) if total else 0

            # 原始返還率: Σ(獎金 × 該獎張數) / (總張數 × 售價)
            full_ev = (
                sum((p.prizeAmount or 0) * (p.totalCount or 0) for p in prizes) / total
                if total else 0.0
            )
            orig_rate = full_ev / price if price else 0.0

            # 現況返還率 (近似): 假設只有頭獎已部分兌領,其餘獎項按比例消耗
            # 剩餘期望值 ≈ (頭獎剩數 × 頭獎金額) + (其他獎項 × (1 - sold_ratio) × 金額)
            grand_amount = c.maxPrizeAmount or (
                max((p.prizeAmount or 0) for p in prizes) if prizes else 0
            )
            grand_left = c.grandPrizeUnclaimed or 0
            other_ev_total = sum(
                (p.prizeAmount or 0) * (p.totalCount or 0)
                for p in prizes
                if (p.prizeAmount or 0) != grand_amount
            )
            other_ev_remaining = other_ev_total * (1 - sold_ratio)
            grand_ev_remaining = grand_amount * grand_left
            cur_ev_per_ticket = (
                (grand_ev_remaining + other_ev_remaining) / remaining_tickets
                if remaining_tickets else 0.0
            )
            cur_rate = cur_ev_per_ticket / price if price else 0.0

            row = {
                "gameId": c.gameId,
                "name": c.name,
                "price": price,
                "issueDate": c.issueDate,
                "redeemDeadline": c.redeemDeadline,
                "daysToRedeem": (redeem - TODAY).days,
                "salesRate": f"{c.salesRateValue:.1f}%",
                "remainingTickets": remaining_tickets,
                "origReturnRate": fmt_pct(orig_rate),
                "currentReturnRate": fmt_pct(cur_rate),
                "rateDelta": fmt_pct(cur_rate - orig_rate),
                "grandPrizeAmount": grand_amount,
                "grandPrizeTotal": c.grandPrizeCount or 0,
                "grandPrizeLeft": grand_left,
                "bigPrizes": big_prize_summary(prizes),
                "_cur_rate_raw": cur_rate,
                "_delta_raw": cur_rate - orig_rate,
            }
            if grand_left > 0:
                group_a.append(row)
            else:
                group_b.append(row)

        # 排序: A 組依「現況返還率」高到低, B 組依距兌獎截止天數短到長
        group_a.sort(key=lambda r: r["_cur_rate_raw"], reverse=True)
        group_b.sort(key=lambda r: r["daysToRedeem"])

        # 寫 CSV
        def write_csv(name: str, rows: list[dict]) -> None:
            path = os.path.join(OUT_DIR, name)
            if not rows:
                # 仍建立空檔便於確認
                open(path, "w", encoding="utf-8-sig").close()
                return
            fieldnames = [k for k in rows[0].keys() if not k.startswith("_")]
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for r in rows:
                    w.writerow({k: r[k] for k in fieldnames})

        write_csv("research_groupA_still_jackpot.csv", group_a)
        write_csv("research_groupB_jackpot_gone.csv", group_b)

        # Markdown 摘要
        def md_table(rows: list[dict], top: int = 30) -> str:
            if not rows:
                return "_(無資料)_\n"
            header = (
                "| 期數 | 名稱 | 售價 | 銷售率 | 距截止 | 原始返還 | 現況返還 | Δ | 頭獎(總/剩) | 大獎結構 |\n"
                "|---|---|---:|---:|---:|---:|---:|---:|---|---|\n"
            )
            lines = [header]
            for r in rows[:top]:
                lines.append(
                    f"| {r['gameId']} | {r['name']} | ${r['price']:,} | {r['salesRate']} | "
                    f"{r['daysToRedeem']}d | {r['origReturnRate']} | {r['currentReturnRate']} | "
                    f"{r['rateDelta']} | {r['grandPrizeTotal']}/{r['grandPrizeLeft']} | "
                    f"{r['bigPrizes']} |"
                )
            return "\n".join(lines)

        md = f"""# YT 影片研究 — 兌獎窗口盤點 ({TODAY.isoformat()})

篩選條件:
- 上市 ≥ 6 個月 (issueDate ≤ {HALF_YEAR_AGO.isoformat()})
- 尚未兌獎截止 (redeemDeadline > {TODAY.isoformat()})
- 已有銷售率資料 (salesRateValue > 0)

跳過 (日期欄缺失): {skipped} 款

## A 組 — 還有頭獎可衝 ({len(group_a)} 款)
依「現況返還率」高到低排序。Δ 正值代表現況返還率比原始返還率高 (有套利空間)。

{md_table(group_a)}

## B 組 — 頭獎已開光 ({len(group_b)} 款)
依「距兌獎截止天數」短到長排序。建議列入不推薦清單。

{md_table(group_b)}

---
完整資料: `research_groupA_still_jackpot.csv` / `research_groupB_jackpot_gone.csv`
"""
        with open(os.path.join(OUT_DIR, "research_summary.md"), "w", encoding="utf-8") as f:
            f.write(md)

        print(f"✅ A 組(頭獎還剩): {len(group_a)} 款")
        print(f"✅ B 組(頭獎開光): {len(group_b)} 款")
        print(f"⚠ 跳過(日期缺失): {skipped} 款")
        print(f"\n輸出檔案:")
        print(f"  - {OUT_DIR}/research_groupA_still_jackpot.csv")
        print(f"  - {OUT_DIR}/research_groupB_jackpot_gone.csv")
        print(f"  - {OUT_DIR}/research_summary.md")

    finally:
        db.close()


if __name__ == "__main__":
    main()
