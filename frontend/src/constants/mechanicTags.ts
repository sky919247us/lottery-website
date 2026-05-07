/**
 * 刮刮樂玩法機制標籤對照表
 * 與 backend/app/service/mechanic_parser_service.py 的白名單一致
 */

export interface MechanicTagMeta {
    /** 內部代碼 */
    code: string
    /** 中文顯示名 */
    label: string
    /** Tooltip 說明 */
    desc: string
    /** Emoji 圖示 (可選) */
    emoji?: string
}

/** 11 種核心玩法機制 + 順序依使用頻率 */
export const MECHANIC_TYPES: MechanicTagMeta[] = [
    { code: 'match_any', label: '任意配對', emoji: '🔢',
      desc: '「您的號碼/符號」對中「幸運號碼」即贏，最常見的玩法' },
    { code: 'match3', label: '三同', emoji: '🎯',
      desc: '刮出 3 個相同金額或符號即贏該獎項' },
    { code: 'bonus_symbol', label: '加碼符號', emoji: '💰',
      desc: '特殊符號保底（如錢袋、紅包），獨立加碼領取' },
    { code: 'bingo_line', label: '賓果連線', emoji: '🎱',
      desc: '版面上連成 1 條線（直/橫/斜）即贏' },
    { code: 'beat_dealer', label: '比大小', emoji: '⚔️',
      desc: '你的點數大於對手即贏該局' },
    { code: 'multiplier', label: '倍數加碼', emoji: '✖️',
      desc: '刮中倍數符號（×2、×5、×10）可乘獎金' },
    { code: 'line_match', label: '連線配對', emoji: '🔗',
      desc: '依連線數量決定獎金（連越多獎越大）' },
    { code: 'sum_target', label: '加總目標', emoji: '➕',
      desc: '符號累計達 N 個查表領對應獎金' },
    { code: 'wild', label: '萬用符號', emoji: '🃏',
      desc: '可取代任何符號的百搭牌，提升中獎機會' },
    { code: 'bonus_game', label: '附加遊戲', emoji: '🎁',
      desc: '主遊戲外的額外關卡（如扭蛋、抽抽樂）' },
    { code: 'lucky_number', label: '幸運號碼', emoji: '🍀',
      desc: '與專屬「幸運號碼區」配對即贏' },
]

/** 複雜度分級 */
export const COMPLEXITY_LEVELS: { score: number; label: string; desc: string }[] = [
    { score: 1, label: '極簡 ⭐', desc: '刮開即知，純配對 / 三同' },
    { score: 2, label: '簡單 ⭐⭐', desc: '單一機制 + 一個附加（保底符號或倍數）' },
    { score: 3, label: '中等 ⭐⭐⭐', desc: '2-3 種機制組合，多區獨立對獎' },
    { score: 4, label: '進階 ⭐⭐⭐⭐', desc: '多重機制 + 連線判讀，需多步驟確認' },
    { score: 5, label: '複雜 ⭐⭐⭐⭐⭐', desc: '5+ 種機制整合，含特殊符號 / 附加遊戲' },
]

/** 用 code 反查 meta */
export function getMechanicMeta(code: string): MechanicTagMeta | undefined {
    return MECHANIC_TYPES.find(m => m.code === code)
}
