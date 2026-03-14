/**
 * Admin Dashboard 首頁
 * 顯示全域營運數據概覽
 */
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Skeleton,
} from '@mui/material'
import StorefrontIcon from '@mui/icons-material/Storefront'
import TicketIcon from '@mui/icons-material/ConfirmationNumber'
import PeopleIcon from '@mui/icons-material/People'
import AssessmentIcon from '@mui/icons-material/Assessment'
import VerifiedIcon from '@mui/icons-material/Verified'
import InventoryIcon from '@mui/icons-material/Inventory'
import PublicIcon from '@mui/icons-material/Public'
import LinkIcon from '@mui/icons-material/Link'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import DescriptionIcon from '@mui/icons-material/Description'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats, fetchTrafficAnalytics } from '../api'

/** 統計卡片元件 */
function StatCard({
  title,
  value,
  icon,
  color,
  loading,
}: {
  title: string
  value: number | string
  icon: React.ReactNode
  color: string
  loading: boolean
}) {
  return (
    <Card
      sx={{
        height: '100%',
        transition: 'all 0.2s',
        '&:hover': { transform: 'translateY(-2px)', boxShadow: '0 8px 24px rgba(0,0,0,0.12)' },
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={500} mb={1}>
              {title}
            </Typography>
            {loading ? (
              <Skeleton width={80} height={40} />
            ) : (
              <Typography variant="h4" fontWeight={700}>
                {typeof value === 'number' ? value.toLocaleString() : value}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}

/** 數據列表小元件 */
function DataList({
  title,
  icon,
  data,
  primaryKey,
  valueKey,
  loading,
}: {
  title: string
  icon: React.ReactNode
  data: any[]
  primaryKey: string
  valueKey: string
  loading: boolean
}) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          {icon}
          <Typography variant="subtitle1" fontWeight={700}>
            {title}
          </Typography>
        </Box>
        {loading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} height={32} />
            ))}
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {data.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                尚無數據
              </Typography>
            ) : (
              data.map((item, idx) => (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderBottom: '1px solid #f0f0f0',
                    pb: 0.5,
                  }}
                >
                  <Typography variant="body2" sx={{ maxWidth: '70%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item[primaryKey]}
                  </Typography>
                  <Typography variant="body2" fontWeight={600} color="primary">
                    {item[valueKey].toLocaleString()}
                  </Typography>
                </Box>
              ))
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

export default function AdminDashboard() {
  const { data: stats, isLoading: loading } = useQuery({
    queryKey: ['dashboardStats'],
    queryFn: fetchDashboardStats,
  })

  const { data: traffic, isLoading: loadingTraffic } = useQuery({
    queryKey: ['trafficAnalytics'],
    queryFn: fetchTrafficAnalytics,
  })

  const statCards = [
    {
      title: '彩券行總數',
      value: stats?.totalRetailers ?? 0,
      icon: <StorefrontIcon />,
      color: '#0B192C',
    },
    {
      title: '台灣彩券',
      value: stats?.twLotteryCount ?? 0,
      icon: <StorefrontIcon />,
      color: '#F39C12',
    },
    {
      title: '台灣運彩',
      value: stats?.sportsLotteryCount ?? 0,
      icon: <StorefrontIcon />,
      color: '#E74C3C',
    },
    {
      title: '營業中',
      value: stats?.activeRetailers ?? 0,
      icon: <VerifiedIcon />,
      color: '#1E8449',
    },
    {
      title: '刮刮樂款式',
      value: stats?.totalScratchcards ?? 0,
      icon: <TicketIcon />,
      color: '#2980B9',
    },
    {
      title: '註冊使用者',
      value: stats?.totalUsers ?? 0,
      icon: <PeopleIcon />,
      color: '#8E44AD',
    },
    {
      title: '庫存回報數',
      value: stats?.totalReports ?? 0,
      icon: <InventoryIcon />,
      color: '#F39C12',
    },
    {
      title: '已認領店家',
      value: stats?.claimedRetailers ?? 0,
      icon: <AssessmentIcon />,
      color: '#D32F2F',
    },
  ]

  return (
    <Box>
      <Grid container spacing={3}>
        {statCards.map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.title}>
            <StatCard {...card} loading={loading} />
          </Grid>
        ))}
      </Grid>

      <Typography variant="h5" fontWeight={700} mt={6} mb={3}>
        流量分析 (最近 7 天)
      </Typography>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <TrendingUpIcon color="primary" />
                <Typography variant="subtitle1" fontWeight={700}>
                  每日造訪趨勢
                </Typography>
              </Box>
              {loadingTraffic ? (
                <Skeleton variant="rectangular" height={250} />
              ) : (
                <Box sx={{ width: '100%', height: 250 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={traffic?.daily || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorVisits" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#1976d2" stopOpacity={0.8}/>
                          <stop offset="95%" stopColor="#1976d2" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                      <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#666' }} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#666' }} />
                      <ChartTooltip
                        contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                      />
                      <Area type="monotone" dataKey="visits" stroke="#1976d2" strokeWidth={3} fillOpacity={1} fill="url(#colorVisits)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <DataList
            title="熱門頁面"
            icon={<DescriptionIcon color="warning" />}
            data={traffic?.topPages || []}
            primaryKey="path"
            valueKey="views"
            loading={loadingTraffic}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <DataList
            title="訪客國家/地區"
            icon={<PublicIcon color="success" />}
            data={traffic?.topCountries || []}
            primaryKey="country"
            valueKey="views"
            loading={loadingTraffic}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <DataList
            title="來源網站"
            icon={<LinkIcon color="info" />}
            data={traffic?.topReferrers || []}
            primaryKey="host"
            valueKey="views"
            loading={loadingTraffic}
          />
        </Grid>
      </Grid>
    </Box>
  )
}
