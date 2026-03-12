import { enqueueSnackbar, type OptionsObject } from 'notistack'

/**
 * 全域 Toast 通知工具
 * 可在 React 元件外部（例如 axios 攔截器）使用
 */
export const toast = {
  success: (msg: string, options?: OptionsObject) => enqueueSnackbar(msg, { variant: 'success', ...options }),
  error: (msg: string, options?: OptionsObject) => enqueueSnackbar(msg, { variant: 'error', ...options }),
  info: (msg: string, options?: OptionsObject) => enqueueSnackbar(msg, { variant: 'info', ...options }),
  warning: (msg: string, options?: OptionsObject) => enqueueSnackbar(msg, { variant: 'warning', ...options }),
}
