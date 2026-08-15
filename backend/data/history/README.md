# 早期刮刮樂歷史資料（本機收集）

產生方式：`cd backend && uv run python scripts/collect_history_scratchcards.py`
（加 `--refresh-news` 會忽略 `_news_cache/` 重抓公告）

**這批資料只落地成檔案，沒有寫進 `scratchcard.db`。**

## 資料來源

台彩官網兩個歷史頁面共用同一支 API：

```
GET https://api.taiwanlottery.com/TLCAPIWeB/Instant/Result
    ?ScratchName=&Start_ListingDate=&End_ListingDate=&PageNum=1&PageSize=500&Type={1|2}
```

| Type | 對應頁面 | 屆別 | 筆數 | 期數範圍 |
|---|---|---|---|---|
| 1 | https://www.taiwanlottery.com/instant/sale | 本屆（2024/1/1 起） | 157 | 5001–5160 |
| 2 | https://www.taiwanlottery.com/instant/history | 上一屆（2024/1/1 前） | 954 | 1–4647 |

獎金結構不在清單 API 裡，另打 `GET /TLCAPIWeB/News/Detail/{newsId}` 取上市公告 HTML，
以「遊戲期數：XXXX」錨點切出該期的表格。解析規則對齊 `app/service/crawler_service.py`。

## 檔案

| 檔案 | 內容 |
|---|---|
| `scratchcards_all.json` | 1111 款完整欄位 + 巢狀 `prizes` 獎金結構 |
| `scratchcards_all.csv` | 一款一列（獎金結構以項數表示），utf-8-sig，Excel 直接開 |
| `prizes_all.csv` | 獎金結構長表：期數 × 獎項名稱 / 獎金金額 / 張數，共 7,419 列 |
| `_news_cache/*.json` | 296 篇上市公告原始 HTML 快取，重跑不會重抓 |
| `_collect_report.json` | 統計、缺值數、失敗清單 |

## 欄位對照

| 需求欄位 | JSON key | 來源 |
|---|---|---|
| 遊戲期數 | `gameId` | `gameVol` |
| 遊戲主題 | `name` | `scratchName` |
| 獎金結構 | `prizes` / `prizeCount` | `News/Detail` 解析 |
| 售價 | `price` | `money` |
| 最高獎金 | `maxPrizeAmount` | `firstPrize` |
| 發行日 | `issueDate` / `issueDateROC` | `listingDate` |
| 下市日 | `endDate` / `endDateROC` | `downDate` |
| 兌獎截止日 | `redeemDeadline` / `redeemDeadlineROC` | `exchangeLastDate` |
| 發行張數 | `totalIssued` | `issuedCount` |
| 銷售率 | `salesRate` / `salesRateValue` | `sales_percent` |
| 頭獎張數 | `grandPrizeCount` | `total_prize` |
| 頭獎未兌領張數 | `grandPrizeUnclaimed` | `remain_prize` |

另附 `term`（屆別）、`scratchId`、`newsId`、`imageUrl`、`prizeInfoUrl`、`endTime`。
日期同時給西元（`issueDate`）與民國（`issueDateROC`，對齊官網顯示）。

## 已知缺漏（都是台彩來源端限制，非爬蟲問題）

1. **386 款沒有獎金結構**：期數 1–386（約 2013 年以前），清單 API 的 `newsId` 為空，
   台彩沒有對應的上市公告可查。
2. **24 款沒有銷售率／頭獎未兌領張數**：期數 5136–5160，都還在售中。
   官網明載「各期彩券之銷售率、頭獎(最高獎金)未兌領張數…於下市後公告」。
   參見記憶檔 `taiwan_lottery_unclaimed_policy.md`。
3. **5 款有 newsId 但抓不到獎金結構**：`4413 鈔票滿天飛`、`4417 樂刮$2,000`、
   `4434 超速777`、`0286 麻將賓果`、`0287 釣大魚`。
   原因是台彩公告內容掛錯——例如標題寫「鈔票滿天飛」與「樂刮$2,000」上市公告的那篇
   （`04thinsetantsaleinfo202044134417`），內文是「無敵777／麻將」那篇的複製；
   `04thinsetantsaleinfo202144294434` 的內文只涵蓋 4429–4433，沒有 4434 的段落。
   腳本已內建「期數 → newsId 反查索引」，但正確的公告在台彩 API 裡根本不存在。

其餘 12 個需求欄位在 1111 筆中缺值數為 0。

## 注意

`crawler_service.py` 的 `fetch_prize_via_api()` 有一個同源 bug：它用
「標題含『遊戲』且有 4 位數字」判斷下一款的分界，導致遊戲主題本身帶年份的款式
（迎向2022、歡慶2016、2021賺翻天、2020向前行、2020520）會在自己的標題就被切斷、
抓不到獎金結構。本腳本改用 `遊戲期數[：:]\d+` 判斷，已修正這 5 款。
生產爬蟲尚未修改。
