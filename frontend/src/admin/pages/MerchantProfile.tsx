/**
 * 商家店舖設定頁面
 * 編輯店家公告 + 硬體設施標籤
 */
import { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Alert,
  Switch,
  Divider,
} from '@mui/material'
import { Save as SaveIcon } from '@mui/icons-material'
import { fetchMyStore, updateMyStore } from '../api'

/** 設施標籤元資料 */
const FACILITY_TAGS = [
  { key: 'hasAC', label: '冷氣', icon: '❄️' },
  { key: 'hasToilet', label: '廁所', icon: '🚻' },
  { key: 'hasSeats', label: '座位', icon: '💺' },
  { key: 'hasWifi', label: 'Wi-Fi', icon: '📶' },
  { key: 'hasAccessibility', label: '無障礙空間', icon: '♿' },
  { key: 'hasEPay', label: '電子支付', icon: '💳' },
  { key: 'hasStrategy', label: '提供攻略', icon: '📋' },
  { key: 'hasNumberPick', label: '挑號服務', icon: '🔢' },
  { key: 'hasScratchBoard', label: '專業刮板', icon: '🪣' },
  { key: 'hasMagnifier', label: '放大鏡', icon: '🔍' },
  { key: 'hasReadingGlasses', label: '老花眼鏡', icon: '👓' },
  { key: 'hasNewspaper', label: '明牌報紙', icon: '📰' },
  { key: 'hasSportTV', label: '運彩轉播', icon: '📺' },
]

export default function MerchantProfile() {
  const [announcement, setAnnouncement] = useState('')
  const [facilities, setFacilities] = useState<Record<string, boolean>>({})
  const [storeName, setStoreName] = useState('')
  const [storeAddress, setStoreAddress] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchMyStore()
        setAnnouncement(data.announcement || '')
        setStoreName(data.name || '')
        setStoreAddress(data.address || '')
        // 初始化設施狀態
        const f: Record<string, boolean> = {}
        for (const tag of FACILITY_TAGS) {
          f[tag.key] = !!data[tag.key]
        }
        setFacilities(f)
      } catch {
        // NOTE: 錯誤由 axios 攔截器統一處理
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  /** 切換單個設施標籤 */
  const toggleFacility = (key: string) => {
    setFacilities(prev => ({ ...prev, [key]: !prev[key] }))
  }

  /** 儲存所有變更（公告 + 設施標籤） */
  const handleSave = async () => {
    setSaving(true)
    setSuccess(false)
    setError('')
    try {
      await updateMyStore({
        announcement,
        ...facilities,
      })
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('儲存失敗，請稍後再試')
    } finally {
      setSaving(false)
    }
  }

  /** 統計已啟用設施數量 */
  const activeCount = Object.values(facilities).filter(Boolean).length

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        店舖設定
      </Typography>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          儲存成功！設施標籤與公告已更新至地圖。
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* 店家基本資訊（唯讀） */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} mb={2}>
            🏪 店家資訊
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <TextField
              label="店名"
              value={storeName}
              disabled
              size="small"
              sx={{ flex: 1, minWidth: 200 }}
            />
            <TextField
              label="地址"
              value={storeAddress}
              disabled
              size="small"
              sx={{ flex: 2, minWidth: 300 }}
            />
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            店名與地址如需修改，請聯繫管理員。
          </Typography>
        </CardContent>
      </Card>

      {/* 店舖公告 */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} mb={2}>
            📢 店舖公告
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={3}
            placeholder="例如：本週最後一批 2000 元面額刮刮樂到貨！"
            value={announcement}
            onChange={(e) => setAnnouncement(e.target.value)}
            disabled={loading}
            helperText="公告內容會顯示在地圖上您的店家資訊中（最多 200 字）"
            slotProps={{
              htmlInput: { maxLength: 200 },
            }}
          />
        </CardContent>
      </Card>

      {/* 硬體設施標籤 */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="subtitle1" fontWeight={600}>
              🏗️ 硬體設施
            </Typography>
            <Typography variant="body2" color="text.secondary">
              已啟用 {activeCount} / {FACILITY_TAGS.length} 項
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
            開啟您的店家有提供的設施，這些資訊將顯示在地圖上吸引更多客人。
          </Typography>

          <Divider sx={{ mb: 2 }} />

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr' },
              gap: 1,
            }}
          >
            {FACILITY_TAGS.map((tag) => (
              <Box
                key={tag.key}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  p: '0.5rem 0.75rem',
                  borderRadius: '10px',
                  border: '1px solid',
                  borderColor: facilities[tag.key]
                    ? 'rgba(212, 175, 55, 0.4)'
                    : 'rgba(0,0,0,0.08)',
                  bgcolor: facilities[tag.key]
                    ? 'rgba(212, 175, 55, 0.06)'
                    : 'transparent',
                  transition: 'all 0.2s',
                  cursor: 'pointer',
                  '&:hover': {
                    borderColor: 'rgba(212, 175, 55, 0.6)',
                    bgcolor: 'rgba(212, 175, 55, 0.04)',
                  },
                }}
                onClick={() => toggleFacility(tag.key)}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography fontSize="1.2rem">{tag.icon}</Typography>
                  <Typography
                    variant="body2"
                    fontWeight={facilities[tag.key] ? 600 : 400}
                    color={facilities[tag.key] ? 'text.primary' : 'text.secondary'}
                  >
                    {tag.label}
                  </Typography>
                </Box>
                <Switch
                  size="small"
                  checked={!!facilities[tag.key]}
                  onChange={() => toggleFacility(tag.key)}
                  onClick={(e) => e.stopPropagation()}
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: '#d4af37',
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      backgroundColor: '#d4af37',
                    },
                  }}
                />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>

      {/* 浮動儲存按鈕 (Floating Action Button) */}
      <Box 
        sx={{ 
          position: 'fixed', 
          bottom: 32, 
          right: 32, 
          zIndex: 1000 
        }}
      >
        <Button
          variant="contained"
          size="large"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={saving || loading}
          sx={{
            background: 'linear-gradient(135deg, #d4af37, #b8962e)',
            '&:hover': { background: 'linear-gradient(135deg, #b8962e, #96790a)' },
            px: 4,
            py: 1.5,
            borderRadius: '30px',
            boxShadow: '0 8px 16px rgba(212, 175, 55, 0.3)',
            fontSize: '1.1rem',
            fontWeight: 600
          }}
        >
          {saving ? '儲存中...' : '儲存變更'}
        </Button>
      </Box>
    </Box>
  )
}
