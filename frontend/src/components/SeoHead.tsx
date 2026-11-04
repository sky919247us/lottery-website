/**
 * SEO 動態 Meta Tags 管理元件
 * 使用 document.title 與 meta 標籤，為每個頁面設定獨立的 SEO 資訊
 * NOTE: 由於此為 SPA，使用原生 DOM 操作更新 meta tags
 */
import { useEffect } from 'react'

interface SeoHeadProps {
  /** 頁面標題（會加上網站名稱後綴） */
  title: string
  /** 頁面描述 */
  description: string
  /** Canonical URL 路徑（如 /detail/123） */
  path?: string
  /** JSON-LD 結構化資料 */
  jsonLd?: Record<string, unknown>
  /** 不希望被搜尋引擎收錄（內容太少的頁面） */
  noindex?: boolean
}

/** 更新或建立 meta 標籤 */
function setMetaTag(property: string, content: string, isOg = false) {
  const attr = isOg ? 'property' : 'name'
  let el = document.querySelector(`meta[${attr}="${property}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, property)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

export default function SeoHead({ title, description, path, jsonLd, noindex }: SeoHeadProps) {
  useEffect(() => {
    const fullTitle = `${title} | 刮刮研究室`
    document.title = fullTitle

    // 基礎 Meta Tags
    setMetaTag('description', description)
    setMetaTag('robots', noindex ? 'noindex, follow' : 'index, follow')

    // Open Graph
    setMetaTag('og:title', fullTitle, true)
    setMetaTag('og:description', description, true)
    if (path) {
      setMetaTag('og:url', `https://i168.win${path}`, true)
    }

    // Twitter Card
    setMetaTag('twitter:title', fullTitle)
    setMetaTag('twitter:description', description)

    // Canonical URL
    if (path) {
      let link = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null
      if (!link) {
        link = document.createElement('link')
        link.setAttribute('rel', 'canonical')
        document.head.appendChild(link)
      }
      link.setAttribute('href', `https://i168.win${path}`)
    }

    // JSON-LD 結構化資料
    if (jsonLd) {
      // 清除之前的動態 JSON-LD
      const existingScript = document.getElementById('dynamic-jsonld')
      if (existingScript) existingScript.remove()
      // 預先產生的靜態頁（scripts/generate-store-pages.mjs）已帶一份，React 接手後改用動態的
      document.getElementById('prerender-jsonld')?.remove()

      const script = document.createElement('script')
      script.id = 'dynamic-jsonld'
      script.type = 'application/ld+json'
      script.textContent = JSON.stringify(jsonLd)
      document.head.appendChild(script)
    }

    return () => {
      // 清除動態 JSON-LD
      const script = document.getElementById('dynamic-jsonld')
      if (script) script.remove()
      // 還原預設 robots，避免 noindex 殘留到下一頁
      if (noindex) setMetaTag('robots', 'index, follow')
    }
  }, [title, description, path, jsonLd, noindex])

  return null
}
