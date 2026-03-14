/**
 * 彩券行管理頁面
 * 使用 MUI DataGrid 呈現所有彩券行資料
 */
import { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  TextField,
  InputAdornment,
  Card,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControlLabel,
  Switch,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
} from '@mui/material'
import { DataGrid, type GridColDef, type GridRowSelectionModel } from '@mui/x-data-grid'
import SearchIcon from '@mui/icons-material/Search'
import EditIcon from '@mui/icons-material/Edit'
import { fetchRetailers, updateRetailer, bulkUpdateRetailerStatus, type RetailerItem } from '../api'
import RetailerLocationPicker from '../components/RetailerLocationPicker'
import 'leaflet/dist/leaflet.css'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '../../utils/toast'

export default function AdminRetailers() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [filterCity, setFilterCity] = useState('')
  const [filterDistrict, setFilterDistrict] = useState('')
  const [searchTimer, setSearchTimer] = useState<ReturnType<typeof setTimeout> | null>(null)

  // 22 縣市列表
  const CITIES = [
    '台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市',
    '基隆市', '新竹市', '新竹縣', '苗栗縣', '彰化縣', '南投縣',
    '雲林縣', '嘉義市', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣',
    '台東縣', '澎湖縣', '金門縣', '連江縣',
  ]

  // 編輯功能狀態
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingRetailer, setEditingRetailer] = useState<RetailerItem | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [selectionModel, setSelectionModel] = useState<GridRowSelectionModel>({ type: 'include', ids: new Set() })
  const [actionLoading, setActionLoading] = useState(false)

  const { data, isLoading: loading } = useQuery({
    queryKey: ['retailers', { page, pageSize, search, filterCity, filterDistrict }],
    queryFn: () => fetchRetailers({
      page: page + 1,
      pageSize,
      search,
      city: filterCity,
      district: filterDistrict,
    })
  })
  const retailers = data?.items || []
  const total = data?.total || 0


  // 當搜尋或篩選器改變時，將頁碼重設為第一頁
  useEffect(() => {
    setPage(0)
  }, [search, filterCity, filterDistrict])

  const handleSearchChange = (value: string) => {
    if (searchTimer) clearTimeout(searchTimer)
    const timer = setTimeout(() => {
      setSearch(value)
      setPage(0)
    }, 400)
    setSearchTimer(timer)
  }

  const handleEditClick = (retailer: RetailerItem) => {
    setEditingRetailer({ ...retailer })
    setError('')
    setEditDialogOpen(true)
  }

  const handleSave = async () => {
    if (!editingRetailer) return
    setSaving(true)
    setError('')
    try {
      await updateRetailer(editingRetailer.id, {
        name: editingRetailer.name,
        address: editingRetailer.address,
        isActive: editingRetailer.isActive,
        isClaimed: editingRetailer.isClaimed,
        merchantTier: editingRetailer.merchantTier,
        district: editingRetailer.district,
        lat: editingRetailer.lat,
        lng: editingRetailer.lng,
        manualRating: editingRetailer.manualRating,
        jackpotCount: editingRetailer.jackpotCount,
      })
      toast.success('彩券行更新成功')
      setEditDialogOpen(false)
      queryClient.invalidateQueries({ queryKey: ['retailers'] })
    } catch (err: any) {
      const msg = err?.response?.data?.detail
      setError(msg || '儲存失敗')
    } finally {
      setSaving(false)
    }
  }

  // 批量更新營業狀態
  const handleBulkStatus = async (isActive: boolean) => {
    const selectedIds = Array.from(selectionModel.ids).map(Number)
    if (selectedIds.length === 0) return
    if (!window.confirm(`確定要將選取的 ${selectedIds.length} 家彩券行設為${isActive ? '營業中' : '停業'}？`)) return
    
    setActionLoading(true)
    try {
      await bulkUpdateRetailerStatus(selectedIds, isActive)
      toast.success(`已將 ${selectedIds.length} 家彩券行設為${isActive ? '營業中' : '停業'}`)
      setSelectionModel({ type: 'include', ids: new Set() })
      queryClient.invalidateQueries({ queryKey: ['retailers'] })
    } finally {
      setActionLoading(false)
    }
  }

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'name', headerName: '名稱', flex: 1, minWidth: 150 },
    { field: 'address', headerName: '地址', flex: 1.5, minWidth: 200 },
    { field: 'city', headerName: '縣市', width: 90 },
    { field: 'district', headerName: '行政區', width: 90 },
    { field: 'jackpotCount', headerName: '頭獎次數', width: 90, renderCell: (params) => params.value ? `🏆 ${params.value}` : '—' },
    { field: 'source', headerName: '來源', width: 100 },
    {
      field: 'isActive',
      headerName: '狀態',
      width: 90,
      renderCell: (params) => (
        <Chip
          label={params.value ? '營業中' : '停業'}
          color={params.value ? 'success' : 'default'}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      field: 'isClaimed',
      headerName: '認領',
      width: 90,
      renderCell: (params) =>
        params.value ? (
          <Chip label="已認領" color="primary" size="small" variant="outlined" />
        ) : (
          <Typography variant="body2" color="text.secondary">—</Typography>
        ),
    },
    {
      field: 'lat',
      headerName: '緯度',
      width: 100,
      renderCell: (params) => (params && params.value !== null && params.value !== undefined) ? Number(params.value).toFixed(5) : '—',
    },
    {
      field: 'lng',
      headerName: '經度',
      width: 100,
      renderCell: (params) => (params && params.value !== null && params.value !== undefined) ? Number(params.value).toFixed(5) : '—',
    },
    {
      field: 'actions',
      headerName: '操作',
      width: 80,
      sortable: false,
      renderCell: (params) => (
        <IconButton
          color="primary"
          size="small"
          onClick={(e) => {
            e.stopPropagation()
            handleEditClick(params.row as RetailerItem)
          }}
        >
          <EditIcon fontSize="small" />
        </IconButton>
      ),
    },
  ]

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h5" fontWeight={700}>
            彩券行管理
          </Typography>
          <Typography variant="body2" color="text.secondary">
            共 {total.toLocaleString()} 筆資料
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            color="success"
            disabled={selectionModel.ids.size === 0 || actionLoading}
            onClick={() => handleBulkStatus(true)}
          >
            設為營業中
          </Button>
          <Button
            variant="outlined"
            color="error"
            disabled={selectionModel.ids.size === 0 || actionLoading}
            onClick={() => handleBulkStatus(false)}
          >
            設為停業
          </Button>
        </Box>
      </Box>

      {/* 篩選列 */}
      <Card sx={{ mb: 3, p: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <TextField
          placeholder="搜尋名稱或地址..."
          size="small"
          sx={{ flex: 1, minWidth: '200px' }}
          onChange={(e) => handleSearchChange(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="action" />
              </InputAdornment>
            ),
          }}
        />
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>縣市</InputLabel>
          <Select
            value={filterCity}
            label="縣市"
            onChange={(e) => setFilterCity(e.target.value)}
          >
            <MenuItem value="">全部</MenuItem>
            {CITIES.map(c => (
              <MenuItem key={c} value={c}>{c}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          placeholder="鄉鎮市區 (例: 中正區)"
          size="small"
          sx={{ width: 150 }}
          value={filterDistrict}
          onChange={(e) => setFilterDistrict(e.target.value)}
        />
      </Card>

      {/* 資料表 */}
      <Card>
        <DataGrid
          rows={retailers}
          columns={columns}
          loading={loading}
          rowCount={total}
          paginationMode="server"
          paginationModel={{ page, pageSize }}
          onPaginationModelChange={(model) => {
            setPage(model.page)
            setPageSize(model.pageSize)
          }}
          pageSizeOptions={[10, 20, 50]}
          disableRowSelectionOnClick
          checkboxSelection
          onRowSelectionModelChange={(newSelection) => setSelectionModel(newSelection)}
          rowSelectionModel={selectionModel}
          autoHeight
          sx={{
            border: 'none',
            '& .MuiDataGrid-columnHeaders': {
              bgcolor: '#F8F9FA',
              fontWeight: 600,
            },
          }}
        />
      </Card>

      {/* 編輯 Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle fontWeight={600}>編輯彩券行</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {editingRetailer && (
            <Box sx={{ pt: 1 }}>
              <TextField
                fullWidth label="名稱" value={editingRetailer.name}
                onChange={(e) => setEditingRetailer({ ...editingRetailer, name: e.target.value })}
                margin="normal" required
              />
              <TextField
                fullWidth label="地址" value={editingRetailer.address}
                onChange={(e) => setEditingRetailer({ ...editingRetailer, address: e.target.value })}
                margin="normal" required
              />
              <FormControl fullWidth margin="normal">
                <InputLabel>權限等級 (merchantTier)</InputLabel>
                <Select
                  value={editingRetailer.merchantTier || 'basic'}
                  label="權限等級 (merchantTier)"
                  onChange={(e) => setEditingRetailer({ ...editingRetailer, merchantTier: e.target.value })}
                >
                  <MenuItem value="basic">基礎版 (basic)</MenuItem>
                  <MenuItem value="pro">專業版 (pro)</MenuItem>
                </Select>
              </FormControl>
              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <TextField
                  label="人工評分 (1~5)"
                  type="number"
                  inputProps={{ step: 0.1, min: 1, max: 5 }}
                  value={editingRetailer.manualRating || ''}
                  onChange={(e) => setEditingRetailer({ ...editingRetailer, manualRating: e.target.value ? Number(e.target.value) : null })}
                  sx={{ flex: 1 }}
                />
                <TextField
                  label="頭獎次數"
                  type="number"
                  inputProps={{ min: 0 }}
                  value={editingRetailer.jackpotCount || ''}
                  onChange={(e) => setEditingRetailer({ ...editingRetailer, jackpotCount: e.target.value ? Number(e.target.value) : 0 })}
                  sx={{ flex: 1 }}
                />
              </Box>
              <Box sx={{ mt: 2, display: 'flex', gap: 4 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={editingRetailer.isActive}
                      onChange={(e) => setEditingRetailer({ ...editingRetailer, isActive: e.target.checked })}
                    />
                  }
                  label="營業中 (isActive)"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={editingRetailer.isClaimed}
                      onChange={(e) => setEditingRetailer({ ...editingRetailer, isClaimed: e.target.checked })}
                    />
                  }
                  label="已認領 (isClaimed)"
                />
              </Box>

              <RetailerLocationPicker
                lat={editingRetailer.lat}
                lng={editingRetailer.lng}
                onChange={(lat, lng) => setEditingRetailer({ ...editingRetailer, lat, lng })}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? '儲存中...' : '儲存'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
