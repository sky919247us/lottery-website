/**
 * 管理員帳號管理頁面
 * 供超級管理員管理後台登入帳號
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
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSnackbar } from 'notistack'
import { fetchAdminUsers, createAdminUser, deleteAdminUser } from '../api'

const ROLES = [
  { value: 'SUPER_ADMIN', label: '超級管理員' },
  { value: 'ADMIN', label: '一般管理員' },
  { value: 'MERCHANT', label: '商家' },
]

export default function AdminAccounts() {
  const queryClient = useQueryClient()
  const { enqueueSnackbar } = useSnackbar()
  const [open, setOpen] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    displayName: '',
    role: 'ADMIN',
    retailerId: '' as string | number,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['adminAccounts'],
    queryFn: fetchAdminUsers,
  })
  const users = Array.isArray(data) ? data : []


  const createMutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: () => {
      enqueueSnackbar('帳號建立成功', { variant: 'success' })
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ['adminAccounts'] })
      setFormData({ username: '', password: '', displayName: '', role: 'ADMIN', retailerId: '' })
    },
    onError: (err: any) => {
      enqueueSnackbar(err.response?.data?.detail || '建立失敗', { variant: 'error' })
    }
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAdminUser,
    onSuccess: () => {
      enqueueSnackbar('帳號已刪除', { variant: 'info' })
      queryClient.invalidateQueries({ queryKey: ['adminAccounts'] })
    }
  })

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
    { field: 'retailerId', headerName: '關聯店家 ID', width: 120 },
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
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>建立帳號</Button>
      </Stack>

      <Card sx={{ height: 600 }}>
        <DataGrid
          rows={users}
          columns={columns}
          loading={isLoading}
          disableRowSelectionOnClick
        />
      </Card>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="xs" fullWidth>
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
          <Button onClick={() => setOpen(false)}>取消</Button>
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
    </Box>
  )
}
