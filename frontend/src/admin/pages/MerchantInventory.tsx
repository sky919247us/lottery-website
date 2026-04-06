/**
 * 商家即時現貨管理頁面
 * 透過搜尋刮刮樂資料庫中的款式來標記庫存狀態
 * 超過兌獎期限的款式不會出現在搜尋結果中
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Alert,
  Divider,
  TextField,
  IconButton,
  Chip,
  Autocomplete,
  CircularProgress,
  Avatar,
} from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import ClockIcon from '@mui/icons-material/AccessTime'
import SearchIcon from '@mui/icons-material/Search'
import {
  fetchMerchantInventory,
  updateMerchantInventory,
  deleteMerchantInventoryItem,
  searchScratchcards,
  type MerchantInventoryItem,
  type ScratchcardOption,
} from '../api'
import { useAdminAuth } from '../AdminAuthContext'

/** 狀態選項 */
const STATUS_OPTIONS = [
  { value: '充足', label: '🟢 充足', color: '#16a34a', bgColor: 'rgba(34, 197, 94, 0.1)' },
  { value: '少量', label: '🟡 少量', color: '#b45309', bgColor: 'rgba(234, 179, 8, 0.1)' },
  { value: '售完', label: '🔴 售完', color: '#dc2626', bgColor: 'rgba(239, 68, 68, 0.1)' },
  { value: '未設定', label: '⚪ 未設定', color: '#94a3b8', bgColor: 'rgba(148, 163, 184, 0.05)' },
]

function formatUpdatedAt(isoStr: string | null | undefined): string {
  if (!isoStr) return '尚未設定'
  const d = new Date(isoStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '剛剛更新'
  if (diffMin < 60) return `${diffMin} 分鐘前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小時前`
  return `${Math.floor(diffHr / 24)} 天前`
}

/** 計算剩餘售完倒數天數 */
function calculateDaysLeft(isoStr: string | null | undefined, status: string): number | null {
  if (!isoStr || !['充足', '少量'].includes(status)) return null
  const d = new Date(isoStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (status === '充足') return Math.max(0, 60 - diffDays)
  if (status === '少量') return Math.max(0, 30 - diffDays)
  return null
}

export default function MerchantInventory() {
  const [items, setItems] = useState<MerchantInventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const { currentRetailerId } = useAdminAuth()

  // 搜尋刮刮樂
  const [showAddForm, setShowAddForm] = useState(false)
  const [searchResults, setSearchResults] = useState<ScratchcardOption[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [selectedCard, setSelectedCard] = useState<ScratchcardOption | null>(null)

  /** 載入庫存資料 */
  const loadInventory = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchMerchantInventory(currentRetailerId ?? undefined)
      setItems(data)
    } catch {
      // NOTE: 錯誤由 axios 攔截器統一處理
    } finally {
      setLoading(false)
    }
  }, [currentRetailerId])

  useEffect(() => { loadInventory() }, [loadInventory])

  /** 搜尋刮刮樂（防抖） */
  useEffect(() => {
    if (!searchInput || searchInput.length < 1) {
      // 無輸入時載入全部可用款式
      if (showAddForm) {
        setSearchLoading(true)
        searchScratchcards('').then(setSearchResults).finally(() => setSearchLoading(false))
      }
      return
    }

    const timer = setTimeout(async () => {
      setSearchLoading(true)
      try {
        const results = await searchScratchcards(searchInput)
        setSearchResults(results)
      } catch {
        setSearchResults([])
      } finally {
        setSearchLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [searchInput, showAddForm])

  /** 開啟新增表單時，預載可用款式 */
  const handleShowAddForm = async () => {
    setShowAddForm(true)
    setSearchLoading(true)
    try {
      const results = await searchScratchcards('')
      setSearchResults(results)
    } catch {
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }

  /** 新增刮刮樂品項 */
  const handleAddItem = () => {
    if (!selectedCard) return
    // 檢查是否已存在
    if (items.some(i => i.scratchcardId === selectedCard.id)) {
      setError('此款式已在庫存清單中')
      return
    }
    setItems(prev => [...prev, {
      itemName: selectedCard.name,
      itemPrice: selectedCard.price,
      status: '未設定',
      scratchcardId: selectedCard.id,
      gameId: selectedCard.gameId,
      imageUrl: selectedCard.imageUrl,
      redeemDeadline: selectedCard.redeemDeadline,
    }])
    setSelectedCard(null)
    setSearchInput('')
    setShowAddForm(false)
  }

  /** 切換單一品項狀態 */
  const setItemStatus = (idx: number, status: string) => {
    setItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, status } : item
    ))
  }

  /** 刪除品項 */
  const handleDeleteItem = async (item: MerchantInventoryItem, idx: number) => {
    if (item.id) {
      try {
        await deleteMerchantInventoryItem(item.id, currentRetailerId ?? undefined)
      } catch {
        setError('刪除失敗')
        return
      }
    }
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  /** 儲存所有變更 */
  const handleSave = async () => {
    setSaving(true)
    setSuccess(false)
    setError('')
    try {
      await updateMerchantInventory(items, currentRetailerId ?? undefined)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
      await loadInventory()
    } catch {
      setError('儲存失敗，請稍後再試')
    } finally {
      setSaving(false)
    }
  }

  /** 統計各狀態數量 */
  const statusCounts = {
    '充足': items.filter(i => i.status === '充足').length,
    '少量': items.filter(i => i.status === '少量').length,
    '售完': items.filter(i => i.status === '售完').length,
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={1}>
        📦 現貨管理
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        從刮刮樂資料庫搜尋款式，快速標記庫存狀態。僅顯示未過兌獎期限的款式。<br/>
        <b>庫存時效規範：</b>為了確保資訊即時，設定為「充足」的款式將於 60 天後自動標示為「售完」；「少量」則為 30 天。每次重新儲存皆會重置倒數。
      </Typography>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          庫存狀態已更新！變更將即時顯示在地圖上。
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* 狀態統計 */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <Chip
          label={`🟢 充足 ${statusCounts['充足']}`}
          sx={{ bgcolor: 'rgba(34, 197, 94, 0.1)', color: '#16a34a', fontWeight: 600 }}
        />
        <Chip
          label={`🟡 少量 ${statusCounts['少量']}`}
          sx={{ bgcolor: 'rgba(234, 179, 8, 0.1)', color: '#b45309', fontWeight: 600 }}
        />
        <Chip
          label={`🔴 售完 ${statusCounts['售完']}`}
          sx={{ bgcolor: 'rgba(239, 68, 68, 0.1)', color: '#dc2626', fontWeight: 600 }}
        />
      </Box>

      {/* 庫存清單 */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 0 }}>
          {items.map((item, idx) => (
            <Box key={`${item.scratchcardId || item.itemName}-${idx}`}>
              {idx > 0 && <Divider />}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  p: '1rem 1.5rem',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                {/* 刮刮樂圖片（若有） */}
                {item.imageUrl && (
                  <Avatar
                    variant="rounded"
                    src={item.imageUrl}
                    alt={item.itemName}
                    sx={{ width: 48, height: 48 }}
                  />
                )}

                {/* 品項名稱 */}
                <Box sx={{ minWidth: 160, flex: '1 0 auto' }}>
                  <Typography fontWeight={600} fontSize="0.95rem">
                    {item.itemName}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.3 }}>
                    <Chip
                      label={`$${item.itemPrice}`}
                      size="small"
                      sx={{ height: 20, fontSize: '0.7rem', bgcolor: 'rgba(212, 175, 55, 0.1)' }}
                    />
                    {item.gameId && (
                      <Typography variant="caption" color="text.secondary">
                        期數: {item.gameId}
                      </Typography>
                    )}
                  </Box>
                  {item.updatedAt && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 0.3, flexWrap: 'wrap' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <ClockIcon sx={{ fontSize: 12 }} />
                        {formatUpdatedAt(item.updatedAt)}
                      </Typography>
                      {calculateDaysLeft(item.updatedAt, item.status) !== null && (
                        <Typography variant="caption" sx={{ 
                          color: item.status === '少量' ? '#b45309' : '#16a34a',
                          fontWeight: 600,
                          bgcolor: item.status === '少量' ? 'rgba(234, 179, 8, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                          px: 0.8,
                          py: 0.2,
                          borderRadius: 1
                        }}>
                          ⏳ 售完倒數 {calculateDaysLeft(item.updatedAt, item.status)} 天
                        </Typography>
                      )}
                    </Box>
                  )}
                </Box>

                {/* 狀態按鈕列 */}
                <Box sx={{ display: 'flex', gap: 0.75, flex: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
                  {STATUS_OPTIONS.map(opt => (
                    <Button
                      key={opt.value}
                      size="small"
                      variant={item.status === opt.value ? 'contained' : 'outlined'}
                      onClick={() => setItemStatus(idx, opt.value)}
                      sx={{
                        minWidth: 80,
                        fontSize: '0.8rem',
                        fontWeight: item.status === opt.value ? 700 : 400,
                        borderColor: item.status === opt.value ? opt.color : 'rgba(0,0,0,0.12)',
                        bgcolor: item.status === opt.value ? opt.bgColor : 'transparent',
                        color: item.status === opt.value ? opt.color : 'text.secondary',
                        '&:hover': {
                          bgcolor: opt.bgColor,
                          borderColor: opt.color,
                        },
                        ...(item.status === opt.value && {
                          boxShadow: `0 0 0 2px ${opt.color}40`,
                        }),
                      }}
                    >
                      {opt.label}
                    </Button>
                  ))}
                </Box>

                {/* 刪除按鈕 */}
                <IconButton
                  size="small"
                  onClick={() => handleDeleteItem(item, idx)}
                  sx={{ color: 'text.secondary' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
          ))}

          {items.length === 0 && !loading && (
            <Box sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
              尚未設定任何庫存品項，點擊下方按鈕從刮刮樂資料庫中新增。
            </Box>
          )}
        </CardContent>
      </Card>

      {/* 新增刮刮樂品項 */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          {!showAddForm ? (
            <Button
              startIcon={<AddIcon />}
              onClick={handleShowAddForm}
              sx={{ color: '#d4af37' }}
            >
              從刮刮樂資料庫新增款式
            </Button>
          ) : (
            <Box>
              <Typography variant="subtitle2" fontWeight={600} mb={1.5}>
                🔍 搜尋刮刮樂款式（輸入名稱或期數）
              </Typography>
              <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <Autocomplete
                  sx={{ flex: 2, minWidth: 280 }}
                  options={searchResults}
                  loading={searchLoading}
                  value={selectedCard}
                  onChange={(_, value) => setSelectedCard(value)}
                  inputValue={searchInput}
                  onInputChange={(_, value) => setSearchInput(value)}
                  getOptionLabel={(option) => `${option.name} ($${option.price})`}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  filterOptions={(x) => x}
                  renderOption={(props, option) => (
                    <li {...props} key={option.id}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
                        {option.imageUrl && (
                          <Avatar
                            variant="rounded"
                            src={option.imageUrl}
                            sx={{ width: 36, height: 36 }}
                          />
                        )}
                        <Box sx={{ flex: 1 }}>
                          <Typography fontSize="0.85rem" fontWeight={600}>
                            {option.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            期數 {option.gameId} ・ ${option.price} ・ 兌獎至 {option.redeemDeadline}
                          </Typography>
                        </Box>
                      </Box>
                    </li>
                  )}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      placeholder="輸入刮刮樂名稱或期數..."
                      size="small"
                      slotProps={{
                        input: {
                          ...params.InputProps,
                          startAdornment: (
                            <>
                              <SearchIcon color="action" sx={{ mr: 0.5 }} />
                              {params.InputProps.startAdornment}
                            </>
                          ),
                          endAdornment: (
                            <>
                              {searchLoading ? <CircularProgress color="inherit" size={20} /> : null}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        },
                      }}
                    />
                  )}
                  noOptionsText="沒有找到符合的款式（可能已過兌獎期限）"
                />
                <Button
                  variant="contained"
                  onClick={handleAddItem}
                  disabled={!selectedCard}
                  sx={{ bgcolor: '#d4af37', '&:hover': { bgcolor: '#b8962e' }, mt: 0.25 }}
                >
                  新增
                </Button>
                <Button
                  onClick={() => { setShowAddForm(false); setSelectedCard(null); setSearchInput('') }}
                  sx={{ mt: 0.25 }}
                >
                  取消
                </Button>
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* 儲存按鈕 */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
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
          }}
        >
          {saving ? '儲存中...' : '儲存庫存狀態'}
        </Button>
      </Box>
    </Box>
  )
}
