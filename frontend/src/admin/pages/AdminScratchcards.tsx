/**
 * 刮刮樂商品管理頁面
 * 顯示所有刮刮樂商品的資料表
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Box,
  Typography,
  Card,
  Chip,
  FormControlLabel,
  Checkbox,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { fetchScratchcards, type ScratchcardItem } from '../api'

export default function AdminScratchcards() {
  const [items, setItems] = useState<ScratchcardItem[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [showExpired, setShowExpired] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchScratchcards({ page: page + 1, pageSize, showExpired })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      // NOTE: 錯誤由 axios 攔截器統一處理
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, showExpired])

  useEffect(() => {
    loadData()
  }, [loadData])

  const columns: GridColDef[] = [
    { field: 'gameId', headerName: '編號', width: 90 },
    { field: 'name', headerName: '名稱', flex: 1, minWidth: 160 },
    {
      field: 'price',
      headerName: '售價',
      width: 100,
      renderCell: (params) => `$${params.value?.toLocaleString() ?? 0}`,
    },
    { field: 'maxPrize', headerName: '最高獎金', width: 130 },
    {
      field: 'totalIssued',
      headerName: '發行張數',
      width: 120,
      renderCell: (params) => params.value?.toLocaleString() ?? '—',
    },
    { field: 'salesRate', headerName: '銷售率', width: 90 },
    {
      field: 'grandPrizeCount',
      headerName: '頭獎張數',
      width: 100,
    },
    {
      field: 'grandPrizeUnclaimed',
      headerName: '未兌領',
      width: 90,
      renderCell: (params) => {
        const value = params.value as number
        return (
          <Chip
            label={value}
            size="small"
            color={value > 0 ? 'error' : 'default'}
            variant={value > 0 ? 'filled' : 'outlined'}
          />
        )
      },
    },
    { field: 'overallWinRate', headerName: '中獎率', width: 90 },
  ]

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          刮刮樂管理
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={showExpired}
                onChange={(e) => {
                  setShowExpired(e.target.checked)
                  setPage(0)
                }}
              />
            }
            label="顯示已截止兌獎"
          />
          <Typography variant="body2" color="text.secondary">
            共 {total} 款
          </Typography>
        </Box>
      </Box>

      <Card sx={{ flex: 1, minHeight: 0 }}>
        <DataGrid
          rows={items}
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
          sx={{
            border: 'none',
            height: '100%',
            '& .MuiDataGrid-columnHeaders': {
              bgcolor: '#F8F9FA',
              fontWeight: 600,
            },
          }}
        />
      </Card>
    </Box>
  )
}
