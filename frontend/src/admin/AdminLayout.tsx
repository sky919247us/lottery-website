/**
 * Admin 後台 Layout
 * MUI Drawer 側邊欄 + AppBar 頂部導航
 * 根據角色動態顯示不同選單
 */
import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  AppBar,
  Box,
  CssBaseline,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Chip,
  useMediaQuery,
  useTheme,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Alert,
  Snackbar,
} from '@mui/material'
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Storefront as StorefrontIcon,
  ConfirmationNumber as TicketIcon,
  People as PeopleIcon,
  Inventory as InventoryIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
  ChevronLeft as ChevronLeftIcon,
  LockReset as LockResetIcon,
  Refresh as RefreshIcon,
  AssignmentTurnedIn as AssignmentTurnedInIcon,
} from '@mui/icons-material'
import { useAdminAuth } from './AdminAuthContext'
import { changeAdminPassword, triggerJackpotSync } from './api'

const DRAWER_WIDTH = 260

/** 角色標籤顏色對應 */
const ROLE_CONFIG: Record<string, { label: string; color: 'error' | 'primary' | 'success' }> = {
  SUPER_ADMIN: { label: '超級管理員', color: 'error' },
  ADMIN: { label: '一般管理員', color: 'primary' },
  MERCHANT: { label: '商家', color: 'success' },
}

export default function AdminLayout() {
  const { admin, logout, isSuperAdmin, isMerchant } = useAdminAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  const [drawerOpen, setDrawerOpen] = useState(!isMobile)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)

  // 變更密碼狀態
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState('')
  const [passwordLoading, setPasswordLoading] = useState(false)

  // 同步頭獎狀態
  const [syncToastOpen, setSyncToastOpen] = useState(false)
  const [syncMessage, setSyncMessage] = useState('')
  const [syncSeverity, setSyncSeverity] = useState<'success' | 'error'>('success')

  const roleConfig = ROLE_CONFIG[admin?.role ?? 'ADMIN']

  /** 管理員側邊欄選單 */
  const adminMenuItems = [
    { label: '營運總覽', icon: <DashboardIcon />, path: '/admin/dashboard' },
    { label: '彩券行管理', icon: <StorefrontIcon />, path: '/admin/retailers' },
    { label: '刮刮樂管理', icon: <TicketIcon />, path: '/admin/scratchcards' },
    { label: '認領審核', icon: <AssignmentTurnedInIcon />, path: '/admin/claims' },
  ]

  /** 超級管理員專屬選單 */
  const superAdminMenuItems = [
    { label: '帳號管理', icon: <PeopleIcon />, path: '/admin/accounts' },
    { label: '社群使用者', icon: <PeopleIcon />, path: '/admin/users' },
  ]

  /** 商家側邊欄選單 */
  const merchantMenuItems = [
    { label: '店舖總覽', icon: <DashboardIcon />, path: '/admin/merchant/dashboard' },
    { label: '店舖設定', icon: <SettingsIcon />, path: '/admin/merchant/profile' },
    { label: '現貨管理', icon: <InventoryIcon />, path: '/admin/merchant/inventory' },
  ]

  /** 根據角色決定要顯示的選單 */
  const menuItems = isMerchant
    ? merchantMenuItems
    : [...adminMenuItems, ...(isSuperAdmin ? superAdminMenuItems : [])]

  const handleNavigation = (path: string) => {
    navigate(path)
    if (isMobile) setDrawerOpen(false)
  }

  const handleLogout = () => {
    setAnchorEl(null)
    logout()
    navigate('/admin/login')
  }

  const handlePasswordSubmit = async () => {
    setPasswordError('')
    setPasswordSuccess('')

    if (!oldPassword || !newPassword || !confirmPassword) {
      setPasswordError('請填寫所有欄位')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('新密碼與確認密碼不相符')
      return
    }

    setPasswordLoading(true)
    try {
      await changeAdminPassword(oldPassword, newPassword)
      setPasswordSuccess('密碼變更成功！請重新登入。')
      setTimeout(() => {
        setPasswordDialogOpen(false)
        handleLogout()
      }, 2000)
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || '變更密碼失敗')
    } finally {
      setPasswordLoading(false)
    }
  }

  const resetPasswordDialog = () => {
    setOldPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setPasswordError('')
    setPasswordSuccess('')
  }

  const handleTriggerSync = async () => {
    setAnchorEl(null)
    try {
      const res = await triggerJackpotSync()
      setSyncSeverity('success')
      setSyncMessage(res.message)
      setSyncToastOpen(true)
    } catch (err: any) {
      setSyncSeverity('error')
      setSyncMessage(err.response?.data?.detail || '觸發同步失敗')
      setSyncToastOpen(true)
    }
  }

  const drawerContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Logo 區域 */}
      <Box sx={{ p: 2.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              background: 'linear-gradient(135deg, #0B192C 0%, #1a2d47 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 900,
              fontSize: 14,
            }}
          >
            刮
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} lineHeight={1.2}>
              刮刮研究室
            </Typography>
            <Typography variant="caption" color="text.secondary">
              管理後台
            </Typography>
          </Box>
        </Box>
        {isMobile && (
          <IconButton onClick={() => setDrawerOpen(false)} size="small">
            <ChevronLeftIcon />
          </IconButton>
        )}
      </Box>
      <Divider />

      {/* 角色標籤 */}
      <Box sx={{ px: 2.5, py: 1.5 }}>
        <Chip
          label={roleConfig.label}
          color={roleConfig.color}
          size="small"
          sx={{ fontWeight: 600 }}
        />
      </Box>

      {/* 導航選單 */}
      <List sx={{ px: 1.5, flex: 1 }}>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <ListItemButton
              key={item.path}
              onClick={() => handleNavigation(item.path)}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                ...(isActive && {
                  bgcolor: 'primary.main',
                  color: 'white',
                  '&:hover': { bgcolor: 'primary.dark' },
                  '& .MuiListItemIcon-root': { color: 'white' },
                }),
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontWeight: isActive ? 600 : 400, fontSize: 14 }}
              />
            </ListItemButton>
          )
        })}
      </List>

      <Divider />

      {/* 底部使用者資訊 */}
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Avatar
          sx={{ width: 36, height: 36, bgcolor: 'primary.main', fontSize: 14, fontWeight: 700 }}
        >
          {admin?.displayName?.charAt(0) || 'A'}
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" fontWeight={600} noWrap>
            {admin?.displayName || admin?.username}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            @{admin?.username}
          </Typography>
        </Box>
      </Box>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <CssBaseline />

      {/* 頂部導航 */}
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          bgcolor: 'background.paper',
          color: 'text.primary',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}
      >
        <Toolbar>
          <IconButton
            edge="start"
            onClick={() => setDrawerOpen(!drawerOpen)}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Box sx={{ flex: 1 }} />
          <IconButton onClick={(e) => setAnchorEl(e.currentTarget)}>
            <Avatar
              sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: 13, fontWeight: 700 }}
            >
              {admin?.displayName?.charAt(0) || 'A'}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MenuItem onClick={() => {
              setAnchorEl(null)
              resetPasswordDialog()
              setPasswordDialogOpen(true)
            }}>
              <LockResetIcon sx={{ mr: 1, fontSize: 18 }} /> 變更密碼
            </MenuItem>
            {isSuperAdmin && (
              <MenuItem onClick={handleTriggerSync}>
                <RefreshIcon sx={{ mr: 1, fontSize: 18 }} /> 強制同步頭獎資料
              </MenuItem>
            )}
            <Divider />
            <MenuItem onClick={handleLogout}>
              <LogoutIcon sx={{ mr: 1, fontSize: 18 }} /> 登出
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* 側邊欄 */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        {/* 手機版 - 可收合 */}
        <Drawer
          variant="temporary"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { width: DRAWER_WIDTH },
          }}
        >
          {drawerContent}
        </Drawer>
        {/* 桌面版 - 固定 */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              width: DRAWER_WIDTH,
              borderRight: '1px solid',
              borderColor: 'divider',
            },
          }}
          open
        >
          {drawerContent}
        </Drawer>
      </Box>

      {/* 主內容區 */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: '64px',
          minHeight: 'calc(100vh - 64px)',
        }}
      >
        <Outlet />
      </Box>

      {/* 變更密碼對話框 */}
      <Dialog
        open={passwordDialogOpen}
        onClose={() => !passwordLoading && setPasswordDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>變更密碼</DialogTitle>
        <DialogContent sx={{ pt: '24px !important' }}>
          {passwordError && <Alert severity="error" sx={{ mb: 2 }}>{passwordError}</Alert>}
          {passwordSuccess && <Alert severity="success" sx={{ mb: 2 }}>{passwordSuccess}</Alert>}
          <TextField
            autoFocus
            margin="dense"
            label="目前密碼"
            type="password"
            fullWidth
            variant="outlined"
            value={oldPassword}
            onChange={e => setOldPassword(e.target.value)}
            disabled={passwordLoading || !!passwordSuccess}
          />
          <TextField
            margin="dense"
            label="新密碼"
            type="password"
            fullWidth
            variant="outlined"
            value={newPassword}
            onChange={e => setNewPassword(e.target.value)}
            disabled={passwordLoading || !!passwordSuccess}
            sx={{ mt: 2 }}
          />
          <TextField
            margin="dense"
            label="確認新密碼"
            type="password"
            fullWidth
            variant="outlined"
            value={confirmPassword}
            onChange={e => setConfirmPassword(e.target.value)}
            disabled={passwordLoading || !!passwordSuccess}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setPasswordDialogOpen(false)} disabled={passwordLoading || !!passwordSuccess}>
            取消
          </Button>
          <Button
            onClick={handlePasswordSubmit}
            variant="contained"
            disabled={passwordLoading || !!passwordSuccess}
          >
            {passwordLoading ? '儲存中...' : '確認變更'}
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* 底部 Toast */}
      <Snackbar 
        open={syncToastOpen} 
        autoHideDuration={4000} 
        onClose={() => setSyncToastOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSyncToastOpen(false)} severity={syncSeverity} sx={{ width: '100%' }}>
          {syncMessage}
        </Alert>
      </Snackbar>

    </Box>
  )
}
