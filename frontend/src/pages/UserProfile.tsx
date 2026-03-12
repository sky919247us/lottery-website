import { useState } from 'react'
import { Box, Typography, Card, LinearProgress, Avatar, Tabs, Tab, List, ListItem, ListItemText, ListItemAvatar, CircularProgress } from '@mui/material'
import { CardGiftcard, LocalMall, Star, VerifiedUser } from '@mui/icons-material'
import { useQuery } from '@tanstack/react-query'
import { fetchAuthMe, fetchKarmaLogs } from '../hooks/api'

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

      <Tabs value={tabValue} onChange={(_, nv) => setTabValue(nv)} variant="fullWidth" sx={{ mb: 2 }}>
        <Tab label="獲取紀錄" />
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
    </Box>
  )
}
