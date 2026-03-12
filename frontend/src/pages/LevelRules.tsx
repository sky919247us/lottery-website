import { Box, Typography, Card, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip } from '@mui/material'

const LEVEL_DATA = [
  { level: 1, title: '初試身手', minPts: 0, perks: '基礎回報庫存' },
  { level: 2, title: '新手玩家', minPts: 50, perks: '回報冷卻降低' },
  { level: 3, title: '進階刮客', minPts: 150, perks: '解鎖店家評價' },
  { level: 4, title: '資深刮客', minPts: 300, perks: '評價權重提升 x1.2' },
  { level: 5, title: '尋寶達人', minPts: 500, perks: '無庫存回報冷卻' },
  { level: 6, title: '刮刮樂大師', minPts: 800, perks: '解鎖專屬稱號標章' },
  { level: 7, title: '情報先鋒', minPts: 1200, perks: '評價權重提升 x1.5' },
  { level: 8, title: '彩券行常客', minPts: 1800, perks: '意見可獲官方首要採納' },
  { level: 9, title: '頭獎雷達', minPts: 2500, perks: '神秘彩蛋解鎖' },
  { level: 10, title: '刮界傳奇', minPts: 5000, perks: '無上榮耀與所有最高權限' },
]

export default function LevelRules() {
  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', p: 2 }}>
      <Typography variant="h5" fontWeight={700} mb={1}>等級與積分規則</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        在刮刮樂情報站，您的每一次貢獻都能帶來積分，隨著等級提升，您將享有更多專屬特權！
      </Typography>

      <Typography variant="h6" fontWeight={700} mb={2}>如何獲得積分？</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 2, mb: 4 }}>
        <Card sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} color="primary">回報庫存</Typography>
          <Typography variant="body2" color="text.secondary">+5 分 / 次</Typography>
          <Typography variant="caption">每日上限 10 次</Typography>
        </Card>
        <Card sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} color="secondary">店家打卡與花費</Typography>
          <Typography variant="body2" color="text.secondary">+10 分 / 次</Typography>
          <Typography variant="caption">需在店家附近</Typography>
        </Card>
        <Card sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} color="warning.main">發布店家評價</Typography>
          <Typography variant="body2" color="text.secondary">+8 分 / 次</Typography>
          <Typography variant="caption">幫忙完善設施標記</Typography>
        </Card>
      </Box>

      <Typography variant="h6" fontWeight={700} mb={2}>等級權限對照表</Typography>
      <TableContainer component={Paper} elevation={0} variant="outlined">
        <Table size="small">
          <TableHead sx={{ bgcolor: 'grey.50' }}>
            <TableRow>
              <TableCell>等級</TableCell>
              <TableCell>稱呼</TableCell>
              <TableCell align="right">所需積分</TableCell>
              <TableCell>專屬特權</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {LEVEL_DATA.map((row) => (
              <TableRow key={row.level}>
                <TableCell>
                  <Chip label={`Lv.${row.level}`} size="small" color={row.level >= 5 ? 'primary' : 'default'} />
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{row.title}</TableCell>
                <TableCell align="right">{row.minPts}</TableCell>
                <TableCell>{row.perks}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  )
}
