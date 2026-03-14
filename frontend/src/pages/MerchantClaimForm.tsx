import { useState } from 'react'
import type { FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Box, Typography, Card, TextField, Button, CircularProgress, Alert } from '@mui/material'
import CloudUpload from '@mui/icons-material/CloudUpload'
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
      
      enqueueSnackbar('認領申請已送出！請靜候 1-2 個工作天審核。', { variant: 'success' })
      navigate(-1) // 回到上一頁

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

  return (
    <Box sx={{ maxWidth: 600, mx: 'auto', p: 2, pt: { xs: 10, md: 12 } }}>
      <Typography variant="h5" fontWeight={700} mb={1}>商家認領申請</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        認領後您將可以維護「{currentStore?.name || '此店家'}」的精確資訊，包含發布公告、調整設施與即時上報庫存狀況。
        目前認領申請為人工審核，請準備清晰之「彩券經銷商證」與「代理人證」照片。
      </Typography>

      <Card sx={{ p: 3 }}>
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
