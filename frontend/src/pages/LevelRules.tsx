import { Box, Typography, Card, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip } from '@mui/material'

/**
 * 等級對照（與後端 backend/app/model/user.py KARMA_LEVELS 同步）
 * 欄位: 等級 / 稱號 / 權重 (回報信心值倍率) / 所需積分
 */
const LEVEL_DATA = [
  { level: 1, title: '刮刮新手', weight: 1, minPts: 0 },
  { level: 2, title: '尋寶學徒', weight: 2, minPts: 100 },
  { level: 3, title: '幸運路人', weight: 4, minPts: 300 },
  { level: 4, title: '資深玩家', weight: 7, minPts: 800 },
  { level: 5, title: '刮刮研究室研究員', weight: 12, minPts: 1500, note: 'YT 頻道初階會員' },
  { level: 6, title: '情報專家', weight: 20, minPts: 3000 },
  { level: 7, title: '彩券達人', weight: 35, minPts: 6000 },
  { level: 8, title: '刮刮研究室金主', weight: 60, minPts: 12000, note: 'YT 頻道高階會員' },
  { level: 9, title: '傳奇財神', weight: 100, minPts: 25000 },
  { level: 10, title: '官方觀察員', weight: 250, minPts: null, note: '手動授予' },
]

/**
 * 積分獲取方式（與後端各 add_karma 呼叫同步）
 * inventory.py: 報庫存 +10 (200m 內) / +3 (距離稍遠)
 * rating.py: 評分店家 +20
 */
const EARN_METHODS = [
  { title: '回報庫存（200m 內）', points: '+10', hint: '需在店家 200m 範圍內', color: 'primary' as const },
  { title: '回報庫存（距離稍遠）', points: '+3', hint: '超出 200m 仍可回報但分數較低', color: 'info' as const },
  { title: '評分 / 評價店家', points: '+20', hint: '對店家發布評分與設施標記', color: 'warning' as const },
  { title: '管理員手動調整', points: '不定', hint: '官方獎勵或會員身分核可', color: 'secondary' as const },
]

export default function LevelRules() {
  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', p: 2 }}>
      <Typography variant="h5" fontWeight={700} mb={1}>等級與積分規則</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        每一次貢獻都能累積積分，等級越高、回報的權重也越高，能更直接影響庫存狀態與店家排序。
      </Typography>

      <Typography variant="h6" fontWeight={700} mb={2}>如何獲得積分？</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 2, mb: 4 }}>
        {EARN_METHODS.map((m) => (
          <Card key={m.title} sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} color={`${m.color}.main`}>{m.title}</Typography>
            <Typography variant="body2" color="text.secondary" fontWeight={700}>{m.points} 分</Typography>
            <Typography variant="caption" color="text.secondary">{m.hint}</Typography>
          </Card>
        ))}
      </Box>

      <Typography variant="h6" fontWeight={700} mb={2}>等級對照表</Typography>
      <TableContainer component={Paper} elevation={0} variant="outlined">
        <Table size="small">
          <TableHead sx={{ bgcolor: 'grey.50' }}>
            <TableRow>
              <TableCell>等級</TableCell>
              <TableCell>稱號</TableCell>
              <TableCell align="right">所需積分</TableCell>
              <TableCell align="right">回報權重</TableCell>
              <TableCell>備註</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {LEVEL_DATA.map((row) => (
              <TableRow key={row.level}>
                <TableCell>
                  <Chip label={`Lv.${row.level}`} size="small" color={row.level >= 5 ? 'primary' : 'default'} />
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{row.title}</TableCell>
                <TableCell align="right">{row.minPts === null ? '—' : row.minPts.toLocaleString()}</TableCell>
                <TableCell align="right">×{row.weight}</TableCell>
                <TableCell sx={{ color: 'text.secondary', fontSize: '0.85rem' }}>{row.note || ''}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
        ※「回報權重」代表您回報的庫存狀態在系統綜合判斷時的影響力倍率。
      </Typography>
    </Box>
  )
}
