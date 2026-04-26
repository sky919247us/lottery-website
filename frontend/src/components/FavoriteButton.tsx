/**
 * 收藏按鈕
 * - 必須登入（綁定 LINE）才能使用
 * - 未登入時顯示提示，點擊導向 LINE 登入
 */
import { useEffect, useState } from 'react'
import { Heart } from 'lucide-react'
import { useSnackbar } from 'notistack'
import { useAuth } from '../hooks/useAuth'
import { addFavorite, checkFavorite, removeFavorite } from '../hooks/api'

interface Props {
    scratchcardId: number
    size?: number
    label?: boolean
}

export default function FavoriteButton({ scratchcardId, size = 20, label = true }: Props) {
    const { isLoggedIn, loginWithLine } = useAuth()
    const { enqueueSnackbar } = useSnackbar()
    const [favorited, setFavorited] = useState(false)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        if (!isLoggedIn || !scratchcardId) return
        checkFavorite(scratchcardId).then(setFavorited).catch(() => { /* ignore */ })
    }, [isLoggedIn, scratchcardId])

    async function handleClick() {
        if (!isLoggedIn) {
            enqueueSnackbar('請先用 LINE 登入才能使用收藏與停售提醒功能', { variant: 'info' })
            setTimeout(() => loginWithLine(), 600)
            return
        }
        if (loading) return
        setLoading(true)
        try {
            if (favorited) {
                await removeFavorite(scratchcardId)
                setFavorited(false)
                enqueueSnackbar('已移除收藏', { variant: 'default' })
            } else {
                await addFavorite(scratchcardId)
                setFavorited(true)
                enqueueSnackbar('已加入收藏，停售前 14 天會在收藏頁出現提醒', { variant: 'success' })
            }
        } catch {
            enqueueSnackbar('操作失敗，請稍後再試', { variant: 'error' })
        } finally {
            setLoading(false)
        }
    }

    return (
        <button
            type="button"
            onClick={handleClick}
            disabled={loading}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.4rem 0.8rem',
                borderRadius: 8,
                border: favorited ? '1px solid #ef4444' : '1px solid #1e3a8a',
                background: favorited ? '#ef4444' : 'transparent',
                color: favorited ? '#ffffff' : '#1e3a8a',
                cursor: loading ? 'wait' : 'pointer',
                fontWeight: 600,
                fontSize: '0.9rem',
                transition: 'all 0.2s',
            }}
            aria-label={favorited ? '取消收藏' : '加入收藏'}
        >
            <Heart size={size} fill={favorited ? '#ffffff' : 'transparent'} />
            {label && (favorited ? '已收藏' : '收藏')}
        </button>
    )
}
