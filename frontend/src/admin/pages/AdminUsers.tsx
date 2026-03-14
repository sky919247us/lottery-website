/**
 * 使用者管理頁面
 * 供超級管理員檢視社群使用者、變更 YouTube 會員積分與等級
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
  Alert,
  List,
  ListItem,
  ListItemText,
  Tab,
  Tabs,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import SearchIcon from '@mui/icons-material/Search'
import HistoryIcon from '@mui/icons-material/History'
import EditIcon from '@mui/icons-material/Edit'
import {
  fetchCommunityUsers,
  fetchCommunityUserHistory,
  adjustCommunityUserKarma,
  bulkBanCommunityUsers,
  type CommunityUserItem,
  type CommunityUserHistory
} from '../api'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '../../utils/toast'

// Tab 面板元件
interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}
function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 2 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

export default function AdminUsers() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [searchTimer, setSearchTimer] = useState<ReturnType<typeof setTimeout> | null>(null)
  const [selectionModel, setSelectionModel] = useState<number[]>([])
  const [actionLoading, setActionLoading] = useState(false)

  // 歷史紀錄 Dialog 狀態
  const [historyOpen, setHistoryOpen] = useState(false)
  const [activeUser, setActiveUser] = useState<CommunityUserItem | null>(null)
  const [userHistory, setUserHistory] = useState<CommunityUserHistory | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [tabValue, setTabValue] = useState(0)

  // 調整積分 Dialog 狀態
  const [adjustOpen, setAdjustOpen] = useState(false)
  const [adjustPoints, setAdjustPoints] = useState<number | string>('')
  const [adjustSetTo, setAdjustSetTo] = useState<number | string>('')
  const [adjustReason, setAdjustReason] = useState('')
  const [adjusting, setAdjusting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const { data, isLoading: loading } = useQuery({
    queryKey: ['communityUsers', { page, pageSize, search }],
    queryFn: () => fetchCommunityUsers({ page: page + 1, pageSize, search }),
  })
  const users = data?.items || []
  const total = data?.total || 0

  // 搜尋變更時重設頁碼
  useEffect(() => {
    setPage(0)
  }, [search])

  const handleSearchChange = (value: string) => {
    if (searchTimer) clearTimeout(searchTimer)
    const timer = setTimeout(() => {
      setSearch(value)
      setPage(0)
    }, 400)
    setSearchTimer(timer)
  }

  // 開啟歷史紀錄 Dialog
  const handleOpenHistory = async (user: CommunityUserItem) => {
    setActiveUser(user)
    setHistoryOpen(true)
    setHistoryLoading(true)
    setTabValue(0)
    try {
      const data = await fetchCommunityUserHistory(user.id)
      setUserHistory(data)
    } catch (err) {
      console.error(err)
    } finally {
      setHistoryLoading(false)
    }
  }

  // 開啟調分 Dialog
  const handleOpenAdjust = (user: CommunityUserItem) => {
    setActiveUser(user)
    setAdjustPoints('')
    setAdjustSetTo('')
    setAdjustReason('')
    setError('')
    setSuccess('')
    setAdjustOpen(true)
  }

  // 送出調分請求
  const handleAdjustSubmit = async () => {
    if (!activeUser) return
    setAdjusting(true)
    setError('')
    setSuccess('')
    try {
      const payload: any = { reason: adjustReason }
      
      // 如果有填寫「直接設定為」，優先使用
      if (adjustSetTo !== '') {
        payload.set_to = Number(adjustSetTo)
      } else if (adjustPoints !== '') {
        payload.points = Number(adjustPoints)
      } else {
        throw new Error('請填寫調整數值或直接設定值')
      }

      await adjustCommunityUserKarma(activeUser.id, payload)
      toast.success('積分調整成功！')
      
      setAdjustOpen(false)
      queryClient.invalidateQueries({ queryKey: ['communityUsers'] })
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || '調整失敗')
    } finally {
      setAdjusting(false)
    }
  }

  // 快捷按鈕：設定為 Youtube 會員
  const handleQuickSet = (points: number, roleName: string) => {
    setAdjustSetTo(points)
    setAdjustPoints('')
    setAdjustReason(`設定為 ${roleName}`)
  }

  // 批量封禁/解封
  const handleBulkBan = async (isBanned: boolean) => {
    if (selectionModel.length === 0) return
    if (!window.confirm(`確定要將選取的 ${selectionModel.length} 名使用者${isBanned ? '封禁' : '解封'}？`)) return
    
    setActionLoading(true)
    try {
      await bulkBanCommunityUsers(selectionModel, isBanned)
      toast.success(`已成功${isBanned ? '封禁' : '解封'} ${selectionModel.length} 名使用者`)
      setSelectionModel([])
      queryClient.invalidateQueries({ queryKey: ['communityUsers'] })
    } finally {
      setActionLoading(false)
    }
  }

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { 
      field: 'displayName', 
      headerName: 'LINE 名稱', 
      flex: 1, 
      minWidth: 150,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {params.row?.pictureUrl && (
            <img src={params.row.pictureUrl} alt="avatar" style={{ width: 24, height: 24, borderRadius: '50%' }} />
          )}
          {params.value || params.row?.customNickname || '未提供'}
        </Box>
      )
    },
    { field: 'karmaLevel', headerName: '等級', width: 80, renderCell: (params) => `Lv.${params.value}` },
    { 
      field: 'levelTitle', 
      headerName: '稱號', 
      width: 150,
      renderCell: (params) => {
        let color: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" = "default"
        if (params.row.karmaLevel >= 8) color = "warning"
        else if (params.row.karmaLevel >= 5) color = "info"
        
        return <Chip label={params.value} color={color} size="small" variant={params.row.karmaLevel >= 5 ? "filled" : "outlined"} />
      }
    },
    { field: 'karmaPoints', headerName: '積分', width: 100 },
    { 
      field: 'createdAt', 
      headerName: '加入時間', 
      width: 160, 
      renderCell: (params) => params.value ? new Date(params.value).toLocaleString() : '' 
    },
    {
      field: 'actions',
      headerName: '操作',
      width: 120,
      renderCell: (params) => (
        <Box>
          <IconButton size="small" color="primary" onClick={() => handleOpenHistory(params.row as CommunityUserItem)} title="歷史紀錄">
            <HistoryIcon />
          </IconButton>
          <IconButton size="small" color="secondary" onClick={() => handleOpenAdjust(params.row as CommunityUserItem)} title="調整積分">
            <EditIcon />
          </IconButton>
        </Box>
      ),
    },
  ]

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">使用者管理</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            color="error"
            disabled={selectionModel.length === 0 || actionLoading}
            onClick={() => handleBulkBan(true)}
          >
            批量封禁
          </Button>
          <Button
            variant="outlined"
            color="success"
            disabled={selectionModel.length === 0 || actionLoading}
            onClick={() => handleBulkBan(false)}
          >
            批量解封
          </Button>
        </Box>
      </Box>

      <Card sx={{ p: 2, mb: 3 }}>
        <TextField
          size="small"
          placeholder="搜尋名稱或 LINE ID..."
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          sx={{ width: 300 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="action" />
              </InputAdornment>
            ),
          }}
        />
      </Card>

      <Card sx={{ height: 650 }}>
        <DataGrid
          rows={users}
          columns={columns}
          loading={loading}
          rowCount={total}
          paginationModel={{ page, pageSize }}
          onPaginationModelChange={(model) => {
            setPage(model.page)
            setPageSize(model.pageSize)
          }}
          paginationMode="server"
          pageSizeOptions={[20, 50, 100]}
          disableRowSelectionOnClick
          checkboxSelection
          onRowSelectionModelChange={(newSelection) => {
            setSelectionModel(newSelection as any)
          }}
          rowSelectionModel={selectionModel as any}
        />
      </Card>

      {/* 調整積分 Dialog */}
      <Dialog open={adjustOpen} onClose={() => !adjusting && setAdjustOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>直接調整積分與等級</DialogTitle>
        <DialogContent dividers>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              目前使用者：{activeUser?.displayName} (Lv.{activeUser?.karmaLevel} {activeUser?.levelTitle})
            </Typography>
            <Typography variant="body2" color="text.secondary">
              目前積分：{activeUser?.karmaPoints}
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
            <Button size="small" variant="outlined" color="primary" onClick={() => handleQuickSet(1500, '研究員 (Lv.5)')}>
              快速設為「研究員 (Lv.5)」
            </Button>
            <Button size="small" variant="outlined" color="warning" onClick={() => handleQuickSet(12000, '金主 (Lv.8)')}>
              快速設為「金主 (Lv.8)」
            </Button>
          </Box>

          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <TextField
              label="增減積分 (例: 100 或 -50)"
              type="number"
              value={adjustPoints}
              onChange={(e) => {
                setAdjustPoints(e.target.value)
                setAdjustSetTo('') // 互斥
              }}
              fullWidth
              disabled={adjusting || adjustSetTo !== ''}
            />
            <Typography sx={{ alignSelf: 'center' }}>或</Typography>
            <TextField
              label="直接設定為 (例: 1500)"
              type="number"
              value={adjustSetTo}
              onChange={(e) => {
                setAdjustSetTo(e.target.value)
                setAdjustPoints('') // 互斥
              }}
              fullWidth
              disabled={adjusting || adjustPoints !== ''}
            />
          </Box>
          
          <TextField
            label="調整原因 (必填，將顯示於 Log)"
            value={adjustReason}
            onChange={(e) => setAdjustReason(e.target.value)}
            fullWidth
            required
            disabled={adjusting}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAdjustOpen(false)} disabled={adjusting}>取消</Button>
          <Button onClick={handleAdjustSubmit} variant="contained" disabled={adjusting || (!adjustPoints && !adjustSetTo) || !adjustReason}>
            {adjusting ? '儲存中...' : '確認調整'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 歷史紀錄 Dialog */}
      <Dialog open={historyOpen} onClose={() => setHistoryOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {activeUser?.displayName} 的歷史紀錄
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          <Tabs value={tabValue} onChange={(_, nv) => setTabValue(nv)} variant="fullWidth">
            <Tab label={`打卡與庫存回報 (${userHistory?.inventoryReports?.length || 0})`} />
            <Tab label={`評分紀錄 (${userHistory?.ratings?.length || 0})`} />
            <Tab label={`Karma 變動 Log (${userHistory?.karmaLogs?.length || 0})`} />
          </Tabs>

          {historyLoading ? (
            <Box sx={{ p: 4, textAlign: 'center' }}><Typography>載入中...</Typography></Box>
          ) : (
             <>
               <TabPanel value={tabValue} index={0}>
                  {userHistory?.inventoryReports?.length === 0 ? (
                    <Typography color="text.secondary">無任何回報紀錄</Typography>
                  ) : (
                    <List disablePadding>
                      {userHistory?.inventoryReports?.map((r: any) => (
                        <ListItem key={r.id} divider>
                          <ListItemText 
                            primary={`回報店家 ID: ${r.retailerId} - 狀態: ${r.status}`} 
                            secondary={`時間: ${new Date(r.createdAt).toLocaleString()} | 紀錄 ID: ${r.id}`} 
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
               </TabPanel>
               <TabPanel value={tabValue} index={1}>
                  {userHistory?.ratings?.length === 0 ? (
                    <Typography color="text.secondary">無任何評分紀錄</Typography>
                  ) : (
                    <List disablePadding>
                      {userHistory?.ratings?.map((r: any) => (
                        <ListItem key={r.id} divider>
                          <ListItemText 
                            primary={`店家 ID: ${r.retailerId} - 評分: ${r.score} 星`} 
                            secondary={`${r.comment || '無評論'} | 時間: ${new Date(r.createdAt).toLocaleString()}`} 
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
               </TabPanel>
               <TabPanel value={tabValue} index={2}>
                  {userHistory?.karmaLogs?.length === 0 ? (
                     <Typography color="text.secondary">無 Karma 變動紀錄</Typography>
                  ) : (
                    <List disablePadding>
                      {userHistory?.karmaLogs?.map((l: any) => (
                        <ListItem key={l.id} divider>
                          <ListItemText 
                            primary={`${l.points > 0 ? '+' : ''}${l.points} 積分 (${l.action})`} 
                            secondary={`${l.description} | 時間: ${new Date(l.createdAt).toLocaleString()}`} 
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
               </TabPanel>
             </>
          )}

        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHistoryOpen(false)}>關閉</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
