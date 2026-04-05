/**
 * 管理員帳號管理頁面
 * 供超級管理員管理後台登入帳號（新增、編輯、刪除）
 */
import { useState } from 'react'
import {
  Box,
  Typography,
  Card,
  Button,
  Stack,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Autocomplete,
  Switch,
  FormControlLabel,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import LockResetIcon from '@mui/icons-material/LockReset'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSnackbar } from 'notistack'
import { fetchAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser, resetAdminPassword, searchRetailers } from '../api'

const ROLES = [
  { value: 'SUPER_ADMIN', label: '超級管理員' },
  { value: 'ADMIN', label: '一般管理員' },
  { value: 'MERCHANT', label: '商家' },
]

export default function AdminAccounts() {
  const queryClient = useQueryClient()
  const { enqueueSnackbar } = useSnackbar()

  // --- 新增對話框 ---
  const [createOpen, setCreateOpen] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    displayName: '',
    role: 'ADMIN',
    retailerId: '' as string | number,
  })

  // --- 編輯對話框 ---
  const [editOpen, setEditOpen] = useState(false)
  const [editData, setEditData] = useState<{
    id: number
    displayName: string
    role: string
    retailerId: string | number
    isActive: boolean
    proExpiresAt: string
    permanentPro: boolean
  } | null>(null)

  // --- 店家搜尋（供關聯使用）---
  const [retailerSearch, setRetailerSearch] = useState('')
  const [retailerOptions, setRetailerOptions] = useState<{ id: number; name: string; address: string }[]>([])

  const { data, isLoading } = useQuery({
    queryKey: ['adminAccounts'],
    queryFn: fetchAdminUsers,
  })
  const users = Array.isArray(data) ? data : []


  const createMutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: () => {
      enqueueSnackbar('帳號建立成功', { variant: 'success' })
      setCreateOpen(false)
      queryClient.invalidateQueries({ queryKey: ['adminAccounts'] })
      setFormData({ username: '', password: '', displayName: '', role: 'ADMIN', retailerId: '' })
    },
    onError: (err: any) => {
      enqueueSnackbar(err.response?.data?.detail || '建立失敗', { variant: 'error' })
    }
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: number; displayName?: string; role?: string; retailerId?: number | null; isActive?: boolean }) =>
      updateAdminUser(id, data),
    onSuccess: () => {
      enqueueSnackbar('帳號更新成功', { variant: 'success' })
      setEditOpen(false)
      queryClient.invalidateQueries({ queryKey: ['adminAccounts'] })
    },
    onError: (err: any) => {
      enqueueSnackbar(err.response?.data?.detail || '更新失敗', { variant: 'error' })
    }
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAdminUser,
    onSuccess: () => {
      enqueueSnackbar('帳號已刪除', { variant: 'info' })
      queryClient.invalidateQueries({ queryKey: ['adminAccounts'] })
    }
  })

  const resetPasswordMutation = useMutation({
    mutationFn: resetAdminPassword,
    onSuccess: (data) => {
      enqueueSnackbar(data.message, { variant: 'success' })
    },
    onError: (err: any) => {
      enqueueSnackbar(err.response?.data?.detail || '重設失敗', { variant: 'error' })
    }
  })

  /** 搜尋店家（防抖） */
  const handleRetailerSearch = async (query: string) => {
    setRetailerSearch(query)
    if (query.length < 2) {
      setRetailerOptions([])
      return
    }
    try {
      const results = await searchRetailers(query)
      setRetailerOptions(results)
    } catch {
      setRetailerOptions([])
    }
  }

  /** 開啟編輯對話框 */
  const handleEditClick = (row: any) => {
    const isPermanent = row.proExpiresAt === '9999-12-31T00:00:00'
    setEditData({
      id: row.id,
      displayName: row.displayName || '',
      role: row.role,
      retailerId: row.retailerId ?? '',
      isActive: !!row.isActive,
      proExpiresAt: row.proExpiresAt ? row.proExpiresAt.slice(0, 10) : '',
      permanentPro: isPermanent,
    })
    setRetailerOptions([])
    setRetailerSearch('')
    setEditOpen(true)
  }

  /** 儲存編輯 */
  const handleSaveEdit = () => {
    if (!editData) return
    const payload: any = {
      id: editData.id,
      displayName: editData.displayName,
      role: editData.role,
      retailerId: editData.retailerId ? Number(editData.retailerId) : null,
      isActive: editData.isActive,
    }
    if (editData.role === 'MERCHANT' && editData.retailerId) {
      if (editData.permanentPro) {
        payload.proExpiresAt = '9999-12-31T00:00:00'
      } else if (editData.proExpiresAt) {
        payload.proExpiresAt = editData.proExpiresAt + 'T00:00:00'
      } else {
        payload.proExpiresAt = null
      }
    }
    updateMutation.mutate(payload)
  }

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'username', headerName: '使用者名稱', width: 150 },
    { field: 'displayName', headerName: '顯示名稱', width: 150 },
    { 
      field: 'role', 
      headerName: '角色', 
      width: 150,
      renderCell: (params) => {
        const role = ROLES.find(r => r.value === params.value)
        return <Chip label={role?.label || params.value} color={params.value === 'SUPER_ADMIN' ? 'error' : 'primary'} size="small" />
      }
    },
    {
      field: 'retailerId',
      headerName: '關聯店家 ID',
      width: 120,
      renderCell: (params) => params.value ? (
        <Chip label={`#${params.value}`} size="small" color="success" variant="outlined" />
      ) : (
        <Typography variant="body2" color="text.secondary">—</Typography>
      )
    },
    {
        field: 'proExpiresAt',
        headerName: 'PRO 到期日',
        width: 160,
        renderCell: (params) => {
          if (!params.value) return <Typography variant="body2" color="text.secondary">—</Typography>
          if (params.value === '9999-12-31T00:00:00') return <Chip label="永久 PRO" size="small" color="info" />
          const d = new Date(params.value)
          const isExpired = d < new Date()
          return <Chip label={d.toLocaleDateString()} size="small" color={isExpired ? 'error' : 'success'} />
        }
    },
    {
        field: 'createdAt',
        headerName: '建立時間',
        width: 180,
        renderCell: (params) => params.value ? new Date(params.value).toLocaleString() : ''
    },
    {
      field: 'actions',
      headerName: '操作',
      width: 160,
      renderCell: (params) => (
        <Stack direction="row" spacing={0.5}>
          <IconButton size="small" color="primary" onClick={() => handleEditClick(params.row)} title="編輯">
            <EditIcon />
          </IconButton>
          <IconButton size="small" color="warning" onClick={() => {
            if(window.confirm(`確定要重設「${params.row.username}」的密碼嗎？\n密碼將重設為帳號名稱「${params.row.username}」`)) {
              resetPasswordMutation.mutate(params.row.id)
            }
          }} title="重設密碼">
            <LockResetIcon />
          </IconButton>
          <IconButton size="small" color="error" onClick={() => {
            if(window.confirm('確定要刪除此管理員帳號嗎？')) {
              deleteMutation.mutate(params.row.id)
            }
          }} disabled={params.row.role === 'SUPER_ADMIN'} title="刪除">
            <DeleteIcon />
          </IconButton>
        </Stack>
      )
    }
  ]

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={700}>後台帳號管理</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>建立帳號</Button>
      </Stack>

      <Card sx={{ height: 600 }}>
        <DataGrid
          rows={users}
          columns={columns}
          loading={isLoading}
          disableRowSelectionOnClick
        />
      </Card>

      {/* ─── 新增帳號對話框 ─── */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>建立管理員帳號</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="帳號 (Username)"
              fullWidth
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            />
            <TextField
              label="密碼"
              type="password"
              fullWidth
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
            <TextField
              label="顯示名稱"
              fullWidth
              value={formData.displayName}
              onChange={(e) => setFormData({ ...formData, displayName: e.target.value })}
            />
            <TextField
              select
              label="角色"
              fullWidth
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            >
              {ROLES.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
            {formData.role === 'MERCHANT' && (
              <TextField
                label="關聯店家 ID"
                type="number"
                fullWidth
                value={formData.retailerId}
                onChange={(e) => setFormData({ ...formData, retailerId: e.target.value })}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>取消</Button>
          <Button 
            variant="contained" 
            onClick={() => createMutation.mutate({
                ...formData,
                retailerId: formData.retailerId ? Number(formData.retailerId) : null
            })}
            disabled={!formData.username || !formData.password || createMutation.isPending}
          >
            確認建立
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── 編輯帳號對話框 ─── */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>編輯管理員帳號</DialogTitle>
        <DialogContent dividers>
          {editData && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField
                label="顯示名稱"
                fullWidth
                value={editData.displayName}
                onChange={(e) => setEditData({ ...editData, displayName: e.target.value })}
              />
              <TextField
                select
                label="角色"
                fullWidth
                value={editData.role}
                onChange={(e) => setEditData({ ...editData, role: e.target.value })}
              >
                {ROLES.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </TextField>

              {/* 關聯店家：支援手動輸入 ID 或搜尋 */}
              <TextField
                label="關聯店家 ID"
                type="number"
                fullWidth
                value={editData.retailerId}
                onChange={(e) => setEditData({ ...editData, retailerId: e.target.value })}
                helperText="輸入彩券行的 ID 編號即可關聯。可在「彩券行管理」頁面查詢 ID。"
              />

              {/* PRO 到期日設定（僅商家角色） */}
              {editData.role === 'MERCHANT' && editData.retailerId && (
                <>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={editData.permanentPro}
                        onChange={(e) => setEditData({
                          ...editData,
                          permanentPro: e.target.checked,
                          proExpiresAt: e.target.checked ? '' : editData.proExpiresAt,
                        })}
                      />
                    }
                    label="永久 PRO"
                  />
                  {!editData.permanentPro && (
                    <TextField
                      label="PRO 到期日"
                      type="date"
                      fullWidth
                      value={editData.proExpiresAt}
                      onChange={(e) => setEditData({ ...editData, proExpiresAt: e.target.value })}
                      slotProps={{ inputLabel: { shrink: true } }}
                      helperText="留空表示非 PRO，設定日期即啟用 PRO"
                    />
                  )}
                </>
              )}

              {/* 搜尋店家名稱輔助 */}
              <Autocomplete
                freeSolo
                options={retailerOptions}
                getOptionLabel={(opt) => typeof opt === 'string' ? opt : `#${opt.id} ${opt.name} (${opt.address})`}
                inputValue={retailerSearch}
                onInputChange={(_, val) => handleRetailerSearch(val)}
                onChange={(_, val) => {
                  if (val && typeof val !== 'string') {
                    setEditData({ ...editData, retailerId: val.id })
                  }
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="搜尋店家名稱（輔助查詢）"
                    placeholder="輸入至少 2 個字搜尋..."
                    size="small"
                  />
                )}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>取消</Button>
          <Button
            variant="contained"
            onClick={handleSaveEdit}
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? '儲存中...' : '儲存變更'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
