/**
 * 刮刮樂共用常數與小工具
 *
 * 與 backend/app/model/ticket_layout.py 同步維護。
 */

/** 面額 → 每本張數對照表 */
export const PRICE_TO_TICKETS_PER_BOOK: Record<number, number> = {
    100: 100,
    200: 100,
    300: 100,
    500: 50,
    1000: 25,
    2000: 19,
}

/** 根據面額取得預設每本張數 */
export function getDefaultTicketsPerBook(price: number): number {
    return PRICE_TO_TICKETS_PER_BOOK[price] || 100
}

/**
 * 熱力圖每列格數
 *
 * 統一 25 欄：100 / 50 / 25 張都能被 25 整除，換行後永遠是完整的列。
 * $2,000 券一本 19 張，單獨用 19 欄，才不會留下殘缺的尾巴。
 */
export function heatmapColumns(ticketsPerBook: number): number {
    return ticketsPerBook % 25 === 0 ? 25 : ticketsPerBook
}
