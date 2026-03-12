/**
 * MUI 自訂主題
 * 整合「刮刮研究室」的查核報告風格：白底、深藍重點色、權威感
 */
import { createTheme } from '@mui/material/styles'

const adminTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#0B192C',
      light: '#1a2d47',
      dark: '#060e1a',
      contrastText: '#fff',
    },
    secondary: {
      main: '#1E8449',
      light: '#27ae60',
      dark: '#145a32',
    },
    error: {
      main: '#D32F2F',
    },
    warning: {
      main: '#F39C12',
    },
    info: {
      main: '#2980B9',
    },
    success: {
      main: '#1E8449',
    },
    background: {
      default: '#F8F9FA',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#0B192C',
      secondary: '#5A6268',
    },
    divider: '#DEE2E6',
  },
  typography: {
    fontFamily: "'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    h4: {
      fontWeight: 700,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 8,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
          backgroundColor: '#F8F9FA',
        },
      },
    },
  },
})

export default adminTheme
