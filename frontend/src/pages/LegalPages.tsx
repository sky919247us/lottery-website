/**
 * 法律與政策頁面（聯絡我們、退換貨政策、商品交付政策）
 * 為 SHOPLINE 等金流平台審核必要頁面
 */
import { Box, Typography, Card, Divider, Link as MuiLink } from '@mui/material'

const Container = ({ children }: { children: React.ReactNode }) => (
  <Box sx={{ maxWidth: 760, mx: 'auto', p: 2, pt: { xs: 10, md: 12 } }}>
    <Card sx={{ p: { xs: 3, md: 5 } }}>{children}</Card>
  </Box>
)

const SectionTitle = ({ children }: { children: React.ReactNode }) => (
  <Typography variant="h6" fontWeight={700} mt={3} mb={1}>{children}</Typography>
)

const Para = ({ children }: { children: React.ReactNode }) => (
  <Typography variant="body2" color="text.secondary" lineHeight={1.9} mb={1.5}>{children}</Typography>
)

const SUPPORT_EMAIL = 'wang4401yt@gmail.com'
const LINE_OA = '@907dlyso'
const LINE_OA_URL = 'https://line.me/R/ti/p/@907dlyso'


/** 聯絡我們 */
export function ContactPage() {
  return (
    <Container>
      <Typography variant="h4" fontWeight={700} mb={1}>聯絡我們</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        刮刮研究室（i168.win）為台灣刮刮樂資訊分析平台。如有任何問題、訂閱諮詢、商家認領協助或申訴需求，請透過以下管道聯繫我們。
      </Typography>

      <Divider sx={{ my: 2 }} />

      <SectionTitle>客服信箱</SectionTitle>
      <Para>
        <MuiLink href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</MuiLink>
        <br />
        我們會於 1–2 個工作天內回覆。為加速處理，請於來信註明：店家名稱（如有）、申請編號、問題描述。
      </Para>

      <SectionTitle>官方 LINE 客服</SectionTitle>
      <Para>
        LINE ID：<MuiLink href={LINE_OA_URL} target="_blank" rel="noopener">{LINE_OA}</MuiLink>
        <br />
        加入官方 LINE 後可即時詢問商家認領、PRO 訂閱與帳號相關問題。
      </Para>

      <SectionTitle>服務時間</SectionTitle>
      <Para>
        週一至週五 10:00–18:00（國定假日除外）。非服務時間之來訊將於下個工作日依序回覆。
      </Para>

      <SectionTitle>網站營運單位</SectionTitle>
      <Para>
        刮刮研究室（個人經營之資訊服務網站）<br />
        網址：<MuiLink href="https://i168.win" target="_blank" rel="noopener">https://i168.win</MuiLink>
      </Para>
    </Container>
  )
}


/** 退換貨政策 */
export function RefundPolicyPage() {
  return (
    <Container>
      <Typography variant="h4" fontWeight={700} mb={1}>退換貨政策</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        最後更新：{new Date().toLocaleDateString('zh-TW')}
      </Typography>

      <Divider sx={{ my: 2 }} />

      <SectionTitle>一、服務性質說明</SectionTitle>
      <Para>
        本站「PRO 商家專業版訂閱」為數位內容服務（線上後台功能權限），屬通訊交易解除權合理例外（依《消費者保護法》第 19 條第 1 項及《通訊交易解除權合理例外情事適用準則》），
        提供之服務一經開通即可立即使用。為保護消費者並避免爭議，本站採用以下退費規則：
      </Para>

      <SectionTitle>二、可全額退費之情形</SectionTitle>
      <Para>
        以下情形，消費者得於付款後 <b>7 日內</b> 來信申請全額退款：
        <ul style={{ marginTop: 8 }}>
          <li>付款完成後，<b>後台權限尚未被開通</b>且消費者尚未登入使用過任何 PRO 功能。</li>
          <li>因系統錯誤導致重複扣款（將退還重複部分）。</li>
          <li>因本站服務故障且 24 小時內未能修復，導致消費者無法使用 PRO 功能。</li>
        </ul>
      </Para>

      <SectionTitle>三、不適用退費之情形</SectionTitle>
      <Para>
        依《通訊交易解除權合理例外情事適用準則》第 2 條第 5 款規定，本服務屬「非以有形媒介提供之數位內容或一經提供即為完成之線上服務」，於消費者開始使用後，
        將不適用 7 日鑑賞期之解約權。具體而言：
        <ul style={{ marginTop: 8 }}>
          <li>後台 PRO 功能<b>已開通並登入使用後</b>，原則上不接受退費。</li>
          <li>訂閱期間若認領之店家被檢舉、違規而導致權限終止者，剩餘訂閱費用不予退還。</li>
          <li>因消費者個人因素（如更換營業項目、結束營業）終止使用，剩餘訂閱費用不予退還，但可提前申請於下一年度免重新認證直接續訂。</li>
        </ul>
      </Para>

      <SectionTitle>四、退費申請方式</SectionTitle>
      <Para>
        如符合上述退費條件，請來信至 <MuiLink href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</MuiLink>，標題註明「PRO 訂閱退費申請」，
        並提供：
        <ul style={{ marginTop: 8 }}>
          <li>付款訂單編號（金流平台提供之交易序號）</li>
          <li>認領之店家名稱與申請編號</li>
          <li>退費原因說明</li>
        </ul>
        我們將於 3–5 個工作天內審核並回覆。經核准後，款項將原路退回原付款金流帳戶，作業時間視銀行/金流而定，通常為 7–14 個工作天。
      </Para>

      <SectionTitle>五、爭議處理</SectionTitle>
      <Para>
        若對退費結果有疑慮，可進一步申訴至消費者保護官（1950）或當地縣市消保官辦公室。本政策若有未盡事宜，依《消費者保護法》及相關法令辦理。
      </Para>
    </Container>
  )
}


/** 商品交付政策 */
export function DeliveryPolicyPage() {
  return (
    <Container>
      <Typography variant="h4" fontWeight={700} mb={1}>商品交付政策</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        最後更新：{new Date().toLocaleDateString('zh-TW')}
      </Typography>

      <Divider sx={{ my: 2 }} />

      <SectionTitle>一、服務內容</SectionTitle>
      <Para>
        本站提供之付費服務為「PRO 商家專業版訂閱」（年費 NT$1,680），為數位後台功能權限服務，並非實體商品，
        故無物流寄送、無收件地址需求，全程於線上完成交付。
      </Para>

      <SectionTitle>二、服務交付流程（SOP）</SectionTitle>
      <Para>
        從下單到取得 PRO 後台權限的完整流程如下：
      </Para>
      <Box component="ol" sx={{ pl: 3, '& li': { mb: 1.5, color: 'text.secondary', lineHeight: 1.8 } }}>
        <li>
          <b>提交認領申請</b>：用戶以 LINE 帳號登入 i168.win，於店家頁面點選「認領」並填寫聯絡資訊、上傳「彩券經銷商證」與「代理人證」照片。
        </li>
        <li>
          <b>人工身份審核</b>：管理員於收件後 <b>1–2 個工作天</b>內審核證件，確認申請人為該店家之合法代理人。審核結果（核准/退件）將透過 LINE 官方帳號通知用戶。
        </li>
        <li>
          <b>選擇方案</b>：審核核准後，用戶可在會員後台選擇「一般認領（永久免費）」或「PRO 專業版（年費 NT$1,680）」。
        </li>
        <li>
          <b>線上付款</b>：選擇 PRO 後將導向第三方金流平台（SHOPLINE / Lemon Squeezy）完成付款。
        </li>
        <li>
          <b>權限自動開通</b>：金流平台付款成功後，系統將於 <b>10 分鐘內</b>自動為該店家帳號啟用 PRO 權限，並透過 LINE 通知用戶。
        </li>
        <li>
          <b>登入使用</b>：用戶使用商家帳號登入 <MuiLink href="https://i168.win/admin" target="_blank" rel="noopener">i168.win/admin</MuiLink> 後台即可開始使用所有 PRO 功能（公告發布、相冊上傳、店家頁面客製等）。
        </li>
      </Box>

      <SectionTitle>三、預期交付時間</SectionTitle>
      <Para>
        <ul style={{ marginTop: 0 }}>
          <li><b>身份審核：</b>1–2 個工作天</li>
          <li><b>付款後權限開通：</b>10 分鐘內（自動化）</li>
          <li><b>整體流程：</b>送出申請 → 取得 PRO 功能，通常於 1–3 個工作天內完成</li>
        </ul>
      </Para>

      <SectionTitle>四、付款失敗或延遲處理</SectionTitle>
      <Para>
        若付款後超過 30 分鐘權限仍未開通，請來信 <MuiLink href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</MuiLink> 並附上付款訂單編號，
        我們將於 1 個工作天內協助確認並手動處理。
      </Para>

      <SectionTitle>五、訂閱有效期</SectionTitle>
      <Para>
        PRO 訂閱自付款開通日起算，效期 <b>365 天</b>。到期前 7 日及 1 日將透過 LINE 提醒，若未續訂則於到期日當天自動降回「一般認領（免費）」狀態，店家認領關係保留，僅 PRO 專屬功能停用。
      </Para>
    </Container>
  )
}
