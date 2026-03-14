import { useState } from 'react'
import { Box, Typography, Card, Chip, Button, Dialog, DialogContent, DialogTitle, Stack } from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import Visibility from '@mui/icons-material/Visibility'
import Check from '@mui/icons-material/Check'
import Close from '@mui/icons-material/Close'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSnackbar } from 'notistack'
import { fetchMerchantClaims, approveMerchantClaim, rejectMerchantClaim } from '../api'

const STATUS_MAP: Record<string, { label: string; color: "warning" | "success" | "error" }> = {
  pending: { label: '待審核', color: 'warning' },
  approved: { label: '已核准', color: 'success' },
  rejected: { label: '已駁回', color: 'error' },
}

export default function AdminClaims() {
  const queryClient = useQueryClient()
  const { enqueueSnackbar } = useSnackbar()
  const [imageDialog, setImageDialog] = useState<{ open: boolean, url: string, title: string }>({ open: false, url: '', title: '' })
  
  // 載入列表
  const { data: claims = [], isLoading } = useQuery({
    queryKey: ['adminClaims'],
    queryFn: () => fetchMerchantClaims()
  })

  // 核准 Mutation
  const approveMutation = useMutation({
    mutationFn: approveMerchantClaim,
    onSuccess: () => {
      enqueueSnackbar('認領申請已核准，商家權限已開通！', { variant: 'success' })
      queryClient.invalidateQueries({ queryKey: ['adminClaims'] })
    },
    onError: (err: any) => {
      enqueueSnackbar(err?.response?.data?.detail || '核准失敗', { variant: 'error' })
    }
  })

  // 駁回 Mutation
  const rejectMutation = useMutation({
    mutationFn: (vars: { id: number, reason: string }) => rejectMerchantClaim(vars.id, vars.reason),
    onSuccess: () => {
      enqueueSnackbar('認領申請已駁回！', { variant: 'info' })
      queryClient.invalidateQueries({ queryKey: ['adminClaims'] })
    },
    onError: (err: any) => {
      enqueueSnackbar(err?.response?.data?.detail || '駁回失敗', { variant: 'error' })
    }
  })

  const openImage = (url: string, title: string) => {
    setImageDialog({ open: true, url, title })
  }

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'retailerId', headerName: '店家ID', width: 90 },
    { field: 'userId', headerName: 'User ID', width: 90 },
    { field: 'contactName', headerName: '聯絡人', width: 120 },
    { field: 'contactPhone', headerName: '聯絡電話', width: 150 },
    { field: 'displayName', headerName: 'LINE 名稱', width: 150 },
    {
      field: 'status',
      headerName: '狀態',
      width: 120,
      renderCell: (params: GridRenderCellParams) => {
        const config = STATUS_MAP[params.value as string] || { label: params.value, color: 'default' }
        return <Chip label={config.label} color={config.color as any} size="small" />
      }
    },
    {
      field: 'createdAt',
      headerName: '申請時間',
      width: 180,
      renderCell: (params: GridRenderCellParams) => new Date(params.value as string).toLocaleString()
    },
    {
      field: 'documents',
      headerName: '證件檢視',
      width: 200,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Stack direction="row" spacing={1} alignItems="center" height="100%">
          <Button size="small" variant="outlined" endIcon={<Visibility />} onClick={() => openImage(params.row.licenseUrl, '經銷證照片')}>
            經銷證
          </Button>
          <Button size="small" variant="outlined" endIcon={<Visibility />} onClick={() => openImage(params.row.idCardUrl, '負責人身分證')}>
            身分證
          </Button>
        </Stack>
      )
    },
    {
      field: 'actions',
      headerName: '審核操作',
      width: 220,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => {
        if (params.row.status !== 'pending') return null
        return (
          <Stack direction="row" spacing={1} alignItems="center" height="100%">
            <Button 
              size="small" variant="contained" color="success" startIcon={<Check />}
              disabled={approveMutation.isPending}
              onClick={() => {
                if(window.confirm('確定要核准此申請嗎？核准後該使用者將獲得商家控制台權限。')) {
                  approveMutation.mutate(params.row.id)
                }
              }}
            >核准</Button>
            <Button 
              size="small" variant="contained" color="error" startIcon={<Close />}
              disabled={rejectMutation.isPending}
              onClick={() => {
                const reason = window.prompt('請輸入駁回原因：')
                if(reason !== null) {
                  rejectMutation.mutate({ id: params.row.id, reason })
                }
              }}
            >駁回</Button>
          </Stack>
        )
      }
    }
  ]

  return (
    <Box sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h5" fontWeight={700} mb={3}>認領申請審核</Typography>
      
      <Card sx={{ flex: 1, minHeight: 500, width: '100%' }}>
        <DataGrid
          rows={claims}
          columns={columns}
          loading={isLoading}
          disableRowSelectionOnClick
          initialState={{
            sorting: { sortModel: [{ field: 'createdAt', sort: 'desc' }] },
          }}
        />
      </Card>

      {/* 圖片檢視 Dialog */}
      <Dialog open={imageDialog.open} onClose={() => setImageDialog({ ...imageDialog, open: false })} maxWidth="md" fullWidth>
        <DialogTitle>{imageDialog.title}</DialogTitle>
        <DialogContent sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
          {imageDialog.url ? (
            <img 
              src={`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}${imageDialog.url}`} 
              alt={imageDialog.title} 
              style={{ maxWidth: '100%', maxHeight: '70vh', objectFit: 'contain' }} 
              onError={(e) => {
                const img = e.target as HTMLImageElement;
                if (!img.src.startsWith('http')) {
                   // 嘗試修正相對路徑
                   img.src = `http://localhost:8000${imageDialog.url}`;
                }
              }}
            />
          ) : (
            <Typography>圖片網址無效</Typography>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  )
}
