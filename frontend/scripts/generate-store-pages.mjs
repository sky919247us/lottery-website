/**
 * 建置後替「可收錄的店家」預先產生靜態頁
 *
 * 網站是 SPA，搜尋引擎抓 /store/:id 只會拿到空殼 index.html。這支腳本在 vite build 之後，
 * 以 dist/index.html 為模板，替 /api/stores/indexable 列出的店家各寫一份
 * dist/store/{id}.html（Cloudflare Pages 會在 /store/{id} 直接送出；用資料夾 index.html
 * 會被 308 轉到結尾帶斜線的網址，和 canonical 不一致）：換上該店的 title、description、canonical、og、
 * LocalBusiness JSON-LD，並在 #root 放一段可讀摘要（React 載入後 createRoot 會整個取代）。
 *
 * - 只產生有內容的店，與 sitemap 同一份清單（generate-sitemap.mjs）。
 * - API 連不上或單店失敗都只略過，不讓 build 失敗。
 *
 * 用法：node scripts/generate-store-pages.mjs   （已掛在 vite build 之後）
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = resolve(ROOT, 'dist')
const SITE = process.env.SITE_ORIGIN || 'https://i168.win'
const API = process.env.VITE_API_BASE || 'https://api.i168.win'
const CONCURRENCY = 6

const htmlEscape = (s) =>
  String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')

/** JSON 放進 <script> 內時，避免 </script> 提早結束標籤 */
const jsonForScript = (obj) => JSON.stringify(obj).replace(/</g, '\\u003c')

async function getJson(path) {
  const res = await fetch(`${API}${path}`, { signal: AbortSignal.timeout(20000) })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** 與 src/pages/StorePage.tsx 的 buildJsonLd 一致 */
function buildJsonLd(d) {
  const ld = {
    '@context': 'https://schema.org',
    '@type': 'LocalBusiness',
    name: d.name,
    url: `${SITE}/store/${d.id}`,
    address: {
      '@type': 'PostalAddress',
      streetAddress: d.address,
      addressLocality: d.district || undefined,
      addressRegion: d.city || undefined,
      addressCountry: 'TW',
    },
  }
  if (d.lat && d.lng) ld.geo = { '@type': 'GeoCoordinates', latitude: d.lat, longitude: d.lng }
  if (d.ratings.totalCount > 0) {
    ld.aggregateRating = {
      '@type': 'AggregateRating',
      ratingValue: d.ratings.avgRating,
      reviewCount: d.ratings.totalCount,
      bestRating: 5,
      worstRating: 1,
    }
  }
  return ld
}

/** 與 StorePage 的 SEO 描述一致（PRO 自訂簡介不在公開 API，這裡一律用摘要） */
function buildDescription(d) {
  const parts = [
    d.jackpots.count > 0 ? `開出 ${d.jackpots.count} 次頭獎` : '',
    d.ratings.totalCount > 0 ? `評分 ${d.ratings.avgRating}（${d.ratings.totalCount} 則）` : '',
    d.winReports.count > 0 ? `近 ${d.winReports.windowDays} 天玩家回報中獎 ${d.winReports.count} 次` : '',
  ].filter(Boolean)
  return `${d.name}，位於${d.address}。${parts.join('、') || '查看頭獎紀錄、玩家評分、中獎回報與庫存。'}`
}

/** #root 內的可讀摘要（給搜尋引擎與未執行 JS 的爬蟲） */
function buildBody(d) {
  const jackpots = d.jackpots.items.slice(0, 20).map((j) =>
    `<li>${htmlEscape(j.gameType)} 第 ${htmlEscape(j.period)} 期 ${htmlEscape(j.drawDate)}</li>`).join('')
  const reviews = d.ratings.recent.filter((r) => r.comment).slice(0, 5).map((r) =>
    `<li>${'★'.repeat(r.rating)} ${htmlEscape(r.comment)}</li>`).join('')
  return [
    '<main>',
    `<h1>${htmlEscape(d.name)}</h1>`,
    `<p>${htmlEscape(d.address)}</p>`,
    d.jackpots.count > 0 ? `<h2>頭獎紀錄（${d.jackpots.count} 次）</h2><ul>${jackpots}</ul>` : '',
    d.ratings.totalCount > 0
      ? `<h2>玩家評價</h2><p>平均 ${d.ratings.avgRating} 分，共 ${d.ratings.totalCount} 則評分</p>${reviews ? `<ul>${reviews}</ul>` : ''}`
      : '',
    d.winReports.count > 0
      ? `<h2>玩家中獎回報</h2><p>近 ${d.winReports.windowDays} 天 ${d.winReports.count} 則，合計 $${Number(d.winReports.totalAmount).toLocaleString('en-US')}</p>`
      : '',
    d.facilities.length > 0 ? `<h2>店內設施</h2><p>${d.facilities.map(htmlEscape).join('、')}</p>` : '',
    '<p><a href="/map">刮刮研究室 中獎地圖</a></p>',
    '</main>',
  ].filter(Boolean).join('')
}

/** 替換 <head> 裡既有的標籤；找不到就插在 </head> 前 */
// replace 的第二參數一律用函式：字串形式會把資料裡的 $&、$' 當成替換樣式解讀
function setHeadTag(html, pattern, replacement) {
  return pattern.test(html)
    ? html.replace(pattern, () => replacement)
    : html.replace('</head>', () => `${replacement}\n</head>`)
}

function renderPage(template, d) {
  const title = htmlEscape(`${d.name}｜頭獎紀錄與評價 | 刮刮研究室`)
  const desc = htmlEscape(buildDescription(d))
  const url = htmlEscape(`${SITE}/store/${d.id}`)
  let html = template
  html = html.replace(/<title>[\s\S]*?<\/title>/, () => `<title>${title}</title>`)
  html = setHeadTag(html, /<meta name="description"[^>]*>/, `<meta name="description" content="${desc}" />`)
  html = setHeadTag(html, /<meta name="robots"[^>]*>/, '<meta name="robots" content="index, follow" />')
  html = setHeadTag(html, /<link rel="canonical"[^>]*>/, `<link rel="canonical" href="${url}" />`)
  html = setHeadTag(html, /<meta property="og:title"[^>]*>/, `<meta property="og:title" content="${title}" />`)
  html = setHeadTag(html, /<meta property="og:description"[^>]*>/, `<meta property="og:description" content="${desc}" />`)
  html = setHeadTag(html, /<meta property="og:url"[^>]*>/, `<meta property="og:url" content="${url}" />`)
  html = setHeadTag(html, /<meta name="twitter:title"[^>]*>/, `<meta name="twitter:title" content="${title}" />`)
  html = setHeadTag(html, /<meta name="twitter:description"[^>]*>/, `<meta name="twitter:description" content="${desc}" />`)
  html = html.replace('</head>', () => `<script type="application/ld+json" id="prerender-jsonld">${jsonForScript(buildJsonLd(d))}</script>\n</head>`)
  html = html.replace('<div id="root"></div>', () => `<div id="root">${buildBody(d)}</div>`)
  return html
}

async function main() {
  const templatePath = resolve(DIST, 'index.html')
  if (!existsSync(templatePath)) {
    console.warn('[store-pages] 找不到 dist/index.html，略過（請先跑 vite build）。')
    return
  }
  const template = readFileSync(templatePath, 'utf8')
  if (!template.includes('<div id="root"></div>')) {
    console.warn('[store-pages] dist/index.html 找不到空的 #root，略過。')
    return
  }

  let stores = []
  try {
    stores = await getJson('/api/stores/indexable')
  } catch (err) {
    console.warn(`[store-pages] 取得可收錄店家清單失敗（${err.message}），略過。`)
    return
  }

  let ok = 0
  let failed = 0
  const queue = [...stores]
  async function worker() {
    while (queue.length) {
      const { id } = queue.shift()
      try {
        const data = await getJson(`/api/stores/${id}/public`)
        const dir = resolve(DIST, 'store')
        mkdirSync(dir, { recursive: true })
        writeFileSync(resolve(dir, `${id}.html`), renderPage(template, data), 'utf8')
        ok += 1
      } catch (err) {
        failed += 1
        console.warn(`[store-pages] 店家 ${id} 失敗（${err.message}），略過。`)
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker))
  console.log(`[store-pages] 已產生 ${ok} 間店家靜態頁${failed ? `，${failed} 間失敗` : ''}（清單共 ${stores.length} 間）`)
}

main().catch((err) => {
  // 任何非預期錯誤都不讓 build 失敗：靜態頁只是 SEO 加分，SPA 本身照常可用
  console.warn(`[store-pages] 非預期錯誤（${err.message}），略過。`)
})
