/**
 * 建置時產生 sitemap.xml
 *
 * 從正式 API 取得目前可索引的刮刮樂款式，加上靜態路由，寫入 public/sitemap.xml。
 *
 * 設計取捨：
 * - 只收「非歷史款」。歷史款（isHistory=true，上一屆 954 款）目前沒有任何 UI 入口，
 *   放進 sitemap 等於製造 954 個孤兒頁 → 索引膨脹 + 稀薄內容風險。等做出歷史款瀏覽頁再納入。
 * - 店家頁（/store/:id，8000+ 筆）同理暫不納入，需先確認每頁有足夠獨立內容。
 * - API 連不上時「保留既有 sitemap.xml 不覆寫」，避免建置失敗或產出空檔。
 *
 * 用法：node scripts/generate-sitemap.mjs   （已掛在 npm run build 之前）
 */
import { writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const OUT = resolve(ROOT, 'public/sitemap.xml')
const SITE = process.env.SITE_ORIGIN || 'https://i168.win'
const API = process.env.VITE_API_BASE || 'https://api.i168.win'

// 靜態路由：只列公開且有獨立內容的頁面
const STATIC_ROUTES = [
  { path: '/', changefreq: 'daily', priority: '1.0' },
  { path: '/calculator', changefreq: 'monthly', priority: '0.8' },
  { path: '/map', changefreq: 'weekly', priority: '0.8' },
  { path: '/videos', changefreq: 'weekly', priority: '0.6' },
  { path: '/unboxing', changefreq: 'weekly', priority: '0.9' },
  { path: '/levels', changefreq: 'monthly', priority: '0.4' },
  { path: '/contact', changefreq: 'yearly', priority: '0.3' },
  { path: '/refund-policy', changefreq: 'yearly', priority: '0.2' },
  { path: '/delivery-policy', changefreq: 'yearly', priority: '0.2' },
]

const xmlEscape = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&apos;')

function urlEntry({ path, changefreq, priority, lastmod }) {
  return [
    '  <url>',
    `    <loc>${xmlEscape(SITE + path)}</loc>`,
    lastmod ? `    <lastmod>${lastmod}</lastmod>` : null,
    `    <changefreq>${changefreq}</changefreq>`,
    `    <priority>${priority}</priority>`,
    '  </url>',
  ].filter(Boolean).join('\n')
}

/** 取回大樣本統計的款式清單，供 /unboxing/:gameId 詳情頁進 sitemap */
async function fetchUnboxingGames() {
  try {
    const res = await fetch(`${API}/api/unboxing/games`, { signal: AbortSignal.timeout(20000) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.warn(`[sitemap] 取得大樣本統計清單失敗（${err.message}），略過該區塊。`)
    return []
  }
}

async function main() {
  let cards = []
  try {
    const res = await fetch(`${API}/api/scratchcards`, { signal: AbortSignal.timeout(20000) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    cards = await res.json()
  } catch (err) {
    console.warn(`[sitemap] 取得款式清單失敗（${err.message}）。`)
    if (existsSync(OUT)) {
      console.warn('[sitemap] 保留既有 public/sitemap.xml，不覆寫。')
      return
    }
    console.warn('[sitemap] 沒有既有檔案，僅輸出靜態路由。')
  }

  const entries = STATIC_ROUTES.map((r) => urlEntry(r))

  for (const c of cards) {
    if (c.isHistory === true) continue  // 歷史款無 UI 入口，不放進 sitemap
    entries.push(urlEntry({ path: `/detail/${c.id}`, changefreq: 'weekly', priority: '0.7' }))
  }

  // 大樣本統計的單款詳情頁：每頁都是獨一無二的實測數據，值得單獨收錄
  const unboxing = await fetchUnboxingGames()
  for (const g of unboxing) {
    entries.push(urlEntry({ path: `/unboxing/${g.gameId}`, changefreq: 'weekly', priority: '0.8' }))
  }

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...entries,
    '</urlset>',
    '',
  ].join('\n')

  writeFileSync(OUT, xml, 'utf8')
  const cardCount = entries.length - STATIC_ROUTES.length - unboxing.length
  console.log(
    `[sitemap] 已寫入 ${OUT}：${entries.length} 個網址（靜態 ${STATIC_ROUTES.length}` +
      ` + 款式 ${cardCount} + 大樣本統計 ${unboxing.length}）`,
  )
}

main()
