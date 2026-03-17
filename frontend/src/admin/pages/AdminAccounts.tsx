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
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSnackbar } from 'notistack'
import { fetchAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser, searchRetailers } from '../api'

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
    setEditData({
      id: row.id,
      displayName: row.displayName || '',
      role: row.role,
      retailerId: row.retailerId ?? '',
      isActive: !!row.isActive,
    })
    setRetailerOptions([])
    setRetailerSearch('')
    setEditOpen(true)
  }

  /** 儲存編輯 */
  const handleSaveEdit = () => {
    if (!editData) return
    updateMutation.mutate({
      id: editData.id,
      displayName: editData.displayName,
      role: editData.role,
      retailerId: editData.retailerId ? Number(editData.retailerId) : null,
      isActive: editData.isActive,
    })
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
        field: 'createdAt', 
        headerName: '建立時間', 
        width: 180,
        renderCell: (params) => params.value ? new Date(params.value).toLocaleString() : ''
    },
    {
      field: 'actions',
      headerName: '操作',
      width: 120,
      renderCell: (params) => (
        <Stack direction="row" spacing={1}>
          <IconButton size="small" color="primary" onClick={() => handleEditClick(params.row)}>
            <EditIcon />
          </IconButton>
          <IconButton size="small" color="error" onClick={() => {
            if(window.confirm('確定要刪除此管理員帳號嗎？')) {
              deleteMutation.mutate(params.row.id)
            }
          }} disabled={params.row.role === 'SUPER_ADMIN'}>
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
