import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Box, Typography, Card, LinearProgress, Avatar, Tabs, Tab, List, ListItem, ListItemText, ListItemAvatar, CircularProgress, Button, Stack, Chip, Table, TableHead, TableBody, TableRow, TableCell } from '@mui/material'
import CardGiftcard from '@mui/icons-material/CardGiftcard'
import LocalMall from '@mui/icons-material/LocalMall'
import Star from '@mui/icons-material/Star'
import VerifiedUser from '@mui/icons-material/VerifiedUser'
import Favorite from '@mui/icons-material/Favorite'
import EmojiEvents from '@mui/icons-material/EmojiEvents'
import { useQuery } from '@tanstack/react-query'
import { fetchAuthMe, fetchKarmaLogs } from '../hooks/api'

/** Karma 等級對照 (與後端 backend/app/model/user.py KARMA_LEVELS 同步) */
const KARMA_LEVELS = [
  { lv: 1, title: '刮刮新手', pts: 0 },
  { lv: 2, title: '尋寶學徒', pts: 100 },
  { lv: 3, title: '幸運路人', pts: 300 },
  { lv: 4, title: '資深玩家', pts: 800 },
  { lv: 5, title: '刮刮研究室研究員', pts: 1500, note: 'YT 初階會員' },
  { lv: 6, title: '情報專家', pts: 3000 },
  { lv: 7, title: '彩券達人', pts: 6000 },
  { lv: 8, title: '刮刮研究室金主', pts: 12000, note: 'YT 高階會員' },
  { lv: 9, title: '傳奇財神', pts: 25000 },
  { lv: 10, title: '官方觀察員', pts: null as number | null, note: '手動授予' },
]

const EARN_METHODS = [
  { title: '🛒 回報庫存（200m 內）', pts: '+10', hint: '在店家 200m 範圍內回報' },
  { title: '📍 回報庫存（遠端）', pts: '+3', hint: '超出 200m 仍可回報但分數較低' },
  { title: '⭐ 評分 / 評價店家', pts: '+20', hint: '對店家發布評分與設施標記' },
  { title: '🎉 中獎打卡', pts: '+5', hint: '在地圖按「中獎打卡」上傳' },
  { title: '🔧 管理員調整', pts: '不定', hint: '官方獎勵或會員身分核可' },
]

// 定義不同操作對應的 Icon
const getActionIcon = (action: string) => {
  switch (action) {
    case 'checkin': return <LocalMall color="primary" />
    case 'report_inventory': return <CardGiftcard color="secondary" />
    case 'rating': return <Star color="warning" />
    case 'system_award': return <VerifiedUser color="success" />
    default: return <VerifiedUser color="disabled" />
  }
}

export default function UserProfile() {
  const [tabValue, setTabValue] = useState(0)
  
  // 取得使用者資料
  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ['authMe'],
    queryFn: fetchAuthMe,
    staleTime: 60 * 1000 // 快取 1 分鐘
  })

  // 取得積分歷史
  const { data: logs, isLoading: logsLoading } = useQuery({
    queryKey: ['karmaLogs', user?.id],
    queryFn: () => fetchKarmaLogs(user!.id),
    enabled: !!user?.id
  })

  if (userLoading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}><CircularProgress /></Box>
  }

  if (!user) {
    return <Box sx={{ p: 3, textAlign: 'center' }}><Typography>請先登入 LINE 以查看個人中心</Typography></Box>
  }

  // 計算進度百分比
  const progress = user.nextLevelPoints 
    ? Math.min(100, (user.karmaPoints / user.nextLevelPoints) * 100) 
    : 100

  return (
    <Box sx={{ maxWidth: 600, mx: 'auto', p: 2 }}>
      <Typography variant="h5" fontWeight={700} mb={2}>個人積分中心</Typography>
      
      {/* 玩家卡片 */}
      <Card sx={{ p: 3, mb: 3, borderRadius: 3, background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)', color: 'white' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Avatar src={user.pictureUrl} sx={{ width: 64, height: 64, border: '2px solid white' }} />
          <Box>
            <Typography variant="h6" fontWeight={700}>{user.customNickname || user.displayName}</Typography>
            <Typography variant="body2" sx={{ opacity: 0.8 }}>
              目前稱號：Lv.{user.karmaLevel} {user.levelTitle}
            </Typography>
          </Box>
        </Box>
        
        <Box sx={{ mt: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2">積分進度：{user.karmaPoints} PTS</Typography>
            {user.karmaLevel < 10 ? (
               <Typography variant="body2">目標：{user.nextLevelPoints} PTS</Typography>
            ) : (
               <Typography variant="body2">已達最高等級</Typography>
            )}
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={progress} 
            sx={{ height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.3)', '& .MuiLinearProgress-bar': { backgroundColor: '#ffd700' } }} 
          />
        </Box>
      </Card>

      {/* 快速捷徑 */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <Button
          component={RouterLink}
          to="/favorites"
          variant="outlined"
          size="small"
          startIcon={<Favorite sx={{ color: '#ef4444' }} />}
          fullWidth
        >
          我的收藏
        </Button>
        <Button
          component={RouterLink}
          to="/levels"
          variant="outlined"
          size="small"
          startIcon={<EmojiEvents sx={{ color: '#f59e0b' }} />}
          fullWidth
        >
          等級與積分規則
        </Button>
      </Stack>

      <Tabs value={tabValue} onChange={(_, nv) => setTabValue(nv)} variant="fullWidth" sx={{ mb: 2 }}>
        <Tab label="獲取紀錄" />
        <Tab label="如何賺積分" />
        <Tab label="等級對照表" />
      </Tabs>

      {tabValue === 0 && (
        <Card sx={{ borderRadius: 2 }}>
          {logsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress size={24} /></Box>
          ) : !logs || logs.length === 0 ? (
            <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 4 }}>
              尚無積分獲取紀錄，趕快去打卡或回報庫存吧！
            </Typography>
          ) : (
            <List>
              {logs.map((log) => (
                <ListItem key={log.id} divider>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: 'grey.100' }}>
                      {getActionIcon(log.action)}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" fontWeight={600}>{log.description}</Typography>
                        <Typography variant="body2" fontWeight={700} color={log.points > 0 ? 'success.main' : 'error.main'}>
                          {log.points > 0 ? '+' : ''}{log.points}
                        </Typography>
                      </Box>
                    }
                    secondary={new Date(log.createdAt).toLocaleString()}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Card>
      )}

      {tabValue === 1 && (
        <Card sx={{ borderRadius: 2, p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1.5}>📈 如何賺積分</Typography>
          <Stack spacing={1.2}>
            {EARN_METHODS.map(m => (
              <Box key={m.title} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 1.5, borderRadius: 1.5, bgcolor: 'grey.50' }}>
                <Box>
                  <Typography variant="body2" fontWeight={600}>{m.title}</Typography>
                  <Typography variant="caption" color="text.secondary">{m.hint}</Typography>
                </Box>
                <Chip label={m.pts} color="success" size="small" sx={{ fontWeight: 700 }} />
              </Box>
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
            ⓘ 等級越高，回報權重越高，影響庫存狀態與店家排序的程度也越大。
          </Typography>
        </Card>
      )}

      {tabValue === 2 && (
        <Card sx={{ borderRadius: 2 }}>
          <Box sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={700}>🏆 等級對照表</Typography>
            <Typography variant="caption" color="text.secondary">目前等級：Lv.{user.karmaLevel} {user.levelTitle}</Typography>
          </Box>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>等級</TableCell>
                <TableCell>稱號</TableCell>
                <TableCell align="right">所需積分</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {KARMA_LEVELS.map(lv => {
                const isCurrent = lv.lv === user.karmaLevel
                return (
                  <TableRow key={lv.lv} sx={isCurrent ? { bgcolor: 'rgba(255, 215, 0, 0.15)' } : {}}>
                    <TableCell>
                      <Chip label={`Lv.${lv.lv}`} size="small" color={isCurrent ? 'warning' : 'default'} />
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" fontWeight={isCurrent ? 700 : 500}>{lv.title}</Typography>
                        {lv.note && (
                          <Typography variant="caption" color="text.secondary">{lv.note}</Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      {lv.pts === null ? '—' : lv.pts.toLocaleString()}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </Box>
  )
}
