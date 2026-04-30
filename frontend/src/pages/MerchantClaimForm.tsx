import { useState } from 'react'
import type { FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Box, Typography, Card, TextField, Button, CircularProgress, Alert, Chip, Divider, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material'
import CloudUpload from '@mui/icons-material/CloudUpload'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CancelIcon from '@mui/icons-material/Cancel'
import StarIcon from '@mui/icons-material/Star'
import { useSnackbar } from 'notistack'
import { useAuth } from '../hooks/useAuth'
import { submitMerchantClaim, uploadImage, fetchRetailers } from '../hooks/api'
import { useQuery } from '@tanstack/react-query'

export default function MerchantClaimForm() {
  const { id } = useParams()
  const retailerId = Number(id)
  const navigate = useNavigate()
  const { enqueueSnackbar } = useSnackbar()
  const { user } = useAuth()
  
  const [contactName, setContactName] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [licenseImage, setLicenseImage] = useState<File | null>(null)
  const [idCardImage, setIdCardImage] = useState<File | null>(null)
  
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  // 取得店家資訊顯示用
  const { data: retailers } = useQuery({
    queryKey: ['retailerDetail', retailerId],
    queryFn: () => fetchRetailers({ city: '', source: '' }), // FIXME: 實作單一尋找 API 或是從外層帶入，為簡化先依賴現有
  })
  
  const currentStore = retailers?.find(r => r.id === retailerId)

  if (!user) {
    return (
      <Box sx={{ p: 4, pt: { xs: 10, md: 12 }, textAlign: 'center' }}>
        <Typography variant="h6">請先登入 LINE 再進行認領。</Typography>
      </Box>
    )
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!licenseImage || !idCardImage || !contactName || !contactPhone) {
      enqueueSnackbar('請完整填寫聯絡資訊並上傳兩張證件照片', { variant: 'warning' })
      return
    }

    try {
      setSubmitting(true)
      
      // 1. 上傳經銷證
      const licenseRes = await uploadImage(licenseImage)
      // 2. 上傳身分證
      const idCardRes = await uploadImage(idCardImage)
      
      // 3. 提交認領
      await submitMerchantClaim({
        retailerId,
        userId: user.id,
        contactName,
        contactPhone,
        licenseUrl: licenseRes.url,
        idCardUrl: idCardRes.url
      })
      
      enqueueSnackbar('認領申請已送出！', { variant: 'success' })
      setSubmitted(true)
      window.scrollTo({ top: 0, behavior: 'smooth' })

    } catch (err: any) {
      console.error(err)
      enqueueSnackbar(err?.response?.data?.detail || '認領提交失敗，請稍後再試', { variant: 'error' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, setter: (f: File | null) => void) => {
    if (e.target.files && e.target.files.length > 0) {
      setter(e.target.files[0])
    }
  }

  if (submitted) {
    const lineAddUrl = 'https://line.me/R/ti/p/@907dlyso'
    return (
      <Box sx={{ maxWidth: 560, mx: 'auto', p: 2, pt: { xs: 10, md: 12 }, textAlign: 'center' }}>
        <Card sx={{ p: 4 }}>
          <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 64, mb: 2 }} />
          <Typography variant="h5" fontWeight={700} mb={1}>認領申請已送出</Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            我們將在 1-2 個工作天內完成審核，審核結果與後台帳號將透過 LINE 通知您。
          </Typography>

          <Alert severity="warning" sx={{ textAlign: 'left', mb: 3 }}>
            <Typography variant="body2" fontWeight={700} mb={0.5}>
              ⚠️ 請務必加入官方 LINE Bot 為好友
            </Typography>
            <Typography variant="body2">
              LINE 規定必須加 Bot 為好友才能收到通知。<b>未加好友將收不到審核結果及後台連結</b>，務必完成此步驟。
            </Typography>
          </Alert>

          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
            <img
              src={`https://qr-official.line.me/sid/L/907dlyso.png`}
              alt="LINE Bot QR Code"
              style={{ width: 200, height: 200, border: '1px solid #ddd', borderRadius: 8 }}
            />
          </Box>

          <Button
            variant="contained"
            color="success"
            fullWidth
            size="large"
            sx={{ mb: 2 }}
            onClick={() => window.open(lineAddUrl, '_blank')}
          >
            立即加入 LINE Bot 好友
          </Button>

          <Typography variant="caption" color="text.secondary" display="block" mb={2}>
            手機 LINE 內請點按鈕；電腦上請用手機掃描上方 QR Code。
          </Typography>

          <Divider sx={{ my: 2 }} />
          <Button variant="text" onClick={() => navigate('/')}>返回首頁</Button>
        </Card>
      </Box>
    )
  }

  return (
    <Box sx={{ maxWidth: 680, mx: 'auto', p: 2, pt: { xs: 10, md: 12 } }}>
      <Typography variant="h5" fontWeight={700} mb={1}>商家認領申請</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        認領後您將可以維護「{currentStore?.name || '此店家'}」的精確資訊，包含發布公告、調整設施與即時上報庫存狀況。
        目前認領申請為人工審核，請準備清晰之「彩券經銷商證」與「代理人證」照片。
      </Typography>

      <Card sx={{ p: 3, mb: 3 }}>
        <form onSubmit={handleSubmit}>
          <Typography variant="subtitle2" fontWeight={600} mb={1}>基本聯絡資訊</Typography>
          <TextField
            fullWidth size="small" label="真實姓名"
            value={contactName} onChange={e => setContactName(e.target.value)}
            sx={{ mb: 2 }} required
          />
          <TextField
            fullWidth size="small" label="聯絡電話"
            value={contactPhone} onChange={e => setContactPhone(e.target.value)}
            sx={{ mb: 3 }} required
            helperText="請填寫方便核對資料之電話"
          />

          <Typography variant="subtitle2" fontWeight={600} mb={1}>驗證文件上傳</Typography>
          <Alert severity="info" sx={{ mb: 2 }}>照片僅做身份查驗之用，我們不會對外公開您的證件資料。</Alert>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
            <Button variant="outlined" component="label" startIcon={<CloudUpload />}>
              {licenseImage ? licenseImage.name : '上傳「彩券經銷商證」照片'}
              <input type="file" hidden accept="image/jpeg, image/png" onChange={e => handleFileChange(e, setLicenseImage)} />
            </Button>

            <Button variant="outlined" component="label" startIcon={<CloudUpload />}>
              {idCardImage ? idCardImage.name : '上傳「代理人證」正面照片'}
              <input type="file" hidden accept="image/jpeg, image/png" onChange={e => handleFileChange(e, setIdCardImage)} />
            </Button>
          </Box>

          <Button
            variant="contained"
            fullWidth
            type="submit"
            disabled={submitting || !licenseImage || !idCardImage}
          >
            {submitting ? <CircularProgress size={24} color="inherit" /> : '確認並送出申請'}
          </Button>
        </form>
      </Card>

      {/* ===== 服務方案說明（金流審核必要資訊） ===== */}
      <Card sx={{ p: 3, mb: 3, border: '1px solid #e0c060', bgcolor: '#fffdf0' }}>
        <Typography variant="h6" fontWeight={700} mb={0.5} display="flex" alignItems="center" gap={1}>
          <StarIcon sx={{ color: '#c8a000', fontSize: 22 }} />
          刮刮研究室 商家服務方案
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          刮刮研究室為台灣刮刮樂投注站資訊平台，提供彩券行業者在平台上管理店家資訊、展示庫存及行銷宣傳的訂閱服務。
        </Typography>

        <Table size="small" sx={{ mb: 2 }}>
          <TableHead>
            <TableRow sx={{ bgcolor: '#f5f5f5' }}>
              <TableCell sx={{ fontWeight: 700 }}>功能項目</TableCell>
              <TableCell align="center" sx={{ fontWeight: 700 }}>一般認領（免費）</TableCell>
              <TableCell align="center" sx={{ fontWeight: 700, color: '#b8860b' }}>
                PRO 專業版（訂閱）
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {[
              { feature: '在地圖與列表上顯示店家', free: true, pro: true },
              { feature: '維護店家基本資訊', free: true, pro: true },
              { feature: '設施標籤管理（冷氣/座位/Wi-Fi…）', free: true, pro: true },
              { feature: '庫存即時更新（顧客可查詢）', free: true, pro: true },
              { feature: '發布店家公告', free: false, pro: true },
              { feature: '地圖排序加權（PRO 優先顯示）', free: false, pro: true },
              { feature: '店家列表置頂（PRO 標章）', free: false, pro: true },
              { feature: '搜尋結果優先排序', free: false, pro: true },
              { feature: '中獎戰績照片上傳（最多 10 張）', free: false, pro: true },
              { feature: '店內環境相冊（最多 10 張）', free: false, pro: true },
              { feature: '專屬店家頁面（完整品牌展示）', free: false, pro: true },
              { feature: '橫幅 Banner 圖片上傳', free: false, pro: true },
              { feature: '店家簡介文字', free: false, pro: true },
              { feature: 'LINE / Facebook / 電話 聯絡資訊展示', free: false, pro: true },
            ].map((row, i) => (
              <TableRow key={i} sx={{ '&:hover': { bgcolor: '#fafafa' } }}>
                <TableCell>{row.feature}</TableCell>
                <TableCell align="center">
                  {row.free
                    ? <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 20 }} />
                    : <CancelIcon sx={{ color: '#ccc', fontSize: 20 }} />}
                </TableCell>
                <TableCell align="center">
                  {row.pro
                    ? <CheckCircleIcon sx={{ color: '#c8a000', fontSize: 20 }} />
                    : <CancelIcon sx={{ color: '#ccc', fontSize: 20 }} />}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Divider sx={{ mb: 2 }} />
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <Box>
            <Chip label="一般認領" size="small" sx={{ mr: 1 }} />
            <Typography component="span" variant="body2" color="text.secondary">永久免費</Typography>
          </Box>
          <Box>
            <Chip label="PRO 專業版" size="small" sx={{ bgcolor: '#c8a000', color: '#fff', mr: 1 }} icon={<StarIcon sx={{ color: '#fff !important', fontSize: 16 }} />} />
            <Typography component="span" variant="body2" fontWeight={600}>年費 NT$1,680</Typography>
          </Box>
        </Box>
        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
          ※ PRO 訂閱費用為數位行銷服務費，透過 SHOPLINE 金流平台收款，支援 LINE Pay、Apple Pay、信用卡。訂閱後可隨時取消，不強制續約。
        </Typography>
      </Card>

      {/* 法律與政策頁面（金流審核必要） */}
      <Card sx={{ p: 2.5, mb: 3, bgcolor: '#fafafa' }}>
        <Typography variant="caption" color="text.secondary" display="block" mb={1.5} fontWeight={600}>
          相關政策說明
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {[
            { label: '聯絡電話 / 信箱', path: '/contact' },
            { label: '退換貨政策', path: '/refund-policy' },
            { label: '商品交付政策', path: '/delivery-policy' },
          ].map((item) => (
            <Typography
              key={item.path}
              variant="body2"
              component="a"
              href={item.path}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                color: 'primary.main',
                textDecoration: 'none',
                fontSize: 13,
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {item.label} →
            </Typography>
          ))}
        </Box>
      </Card>

      {/* 僅當表單填寫完畢才顯示 LINE 客服，避免被濫用 */}
      {(contactName.trim() && contactPhone.trim() && licenseImage && idCardImage) ? (
        <Box sx={{ mt: 3, pt: 3, borderTop: '1px solid #eee', textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary" mb={1}>
            需要提供進一步證明文件或遇到問題？
          </Typography>
          <Button variant="contained" color="success" onClick={() => window.open('https://line.me/R/ti/p/@907dlyso', '_blank')}>
            聯絡官方 LINE 客服
          </Button>
        </Box>
      ) : null}
    </Box>
  )
}
