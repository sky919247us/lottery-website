/**
 * 商家專屬頁面後台編輯器
 * 提供商家編輯專屬頁面資訊、上傳 Banner、相簿與中獎牆圖片
 */
import { useState, useEffect, useRef } from 'react'
import {
    Box, Typography, Card, CardContent, TextField, Button,
    Alert, IconButton, Chip, Dialog, DialogTitle,
    DialogContent, DialogActions, CircularProgress,
} from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import AddPhotoAlternateIcon from '@mui/icons-material/AddPhotoAlternate'
import DeleteIcon from '@mui/icons-material/Delete'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import {
    fetchMyStore, updateStorePage, uploadStorePhoto,
    deleteStorePhoto, uploadStoreBanner, fetchMerchantPhotos,
} from '../api'
import { useAdminAuth } from '../AdminAuthContext'

export default function MerchantStorePage() {
    const { currentRetailerId } = useAdminAuth()

    // 文字資訊
    const [description, setDescription] = useState('')
    const [businessHours, setBusinessHours] = useState('')
    const [contactLine, setContactLine] = useState('')
    const [contactFb, setContactFb] = useState('')
    const [contactPhone, setContactPhone] = useState('')
    const [bannerUrl, setBannerUrl] = useState('')

    // 圖片
    const [galleryPhotos, setGalleryPhotos] = useState<any[]>([])
    const [winningWallPhotos, setWinningWallPhotos] = useState<any[]>([])

    // UI 狀態
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [success, setSuccess] = useState('')
    const [error, setError] = useState('')

    // 上傳對話框
    const [uploadDialog, setUploadDialog] = useState(false)
    const [uploadCategory, setUploadCategory] = useState<'gallery' | 'winning_wall'>('gallery')
    const [uploadCaption, setUploadCaption] = useState('')
    const fileInputRef = useRef<HTMLInputElement>(null)
    const bannerInputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        loadData()
    }, [currentRetailerId])

    async function loadData() {
        try {
            setLoading(true)
            const rid = currentRetailerId ?? undefined
            const data = await fetchMyStore(rid)
            setDescription(data.description || '')
            setBusinessHours(data.businessHours || '')
            setContactLine(data.contactLine || '')
            setContactFb(data.contactFb || '')
            setContactPhone(data.contactPhone || '')
            setBannerUrl(data.bannerUrl || '')

            // 圖片從後台專用 API 取得（僅 PRO 商家）
            try {
                const photosData = await fetchMerchantPhotos(rid)
                setGalleryPhotos(photosData.gallery || [])
                setWinningWallPhotos(photosData.winningWall || [])
            } catch {
                // 尚無照片
            }
        } catch {
            setError('載入失��，請重新整理')
        } finally {
            setLoading(false)
        }
    }

    /** 儲存文字資訊 */
    async function handleSave() {
        setSaving(true)
        setSuccess('')
        setError('')
        try {
            await updateStorePage({
                description,
                businessHours,
                contactLine,
                contactFb,
                contactPhone,
            }, currentRetailerId ?? undefined)
            setSuccess('專屬頁面資訊已儲存！')
            setTimeout(() => setSuccess(''), 3000)
        } catch {
            setError('儲存失敗，請稍後再試')
        } finally {
            setSaving(false)
        }
    }

    /** 上傳 Banner */
    async function handleBannerUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0]
        if (!file) return
        setUploading(true)
        try {
            const res = await uploadStoreBanner(file, currentRetailerId ?? undefined)
            setBannerUrl(res.bannerUrl)
            setSuccess('Banner 已更新！')
            setTimeout(() => setSuccess(''), 3000)
        } catch {
            setError('Banner 上傳失敗')
        } finally {
            setUploading(false)
        }
    }

    /** 開啟上傳圖片對話框 */
    function openUploadDialog(category: 'gallery' | 'winning_wall') {
        setUploadCategory(category)
        setUploadCaption('')
        setUploadDialog(true)
    }

    /** 上傳圖片 */
    async function handlePhotoUpload() {
        const file = fileInputRef.current?.files?.[0]
        if (!file) return
        setUploading(true)
        try {
            const res = await uploadStorePhoto(file, uploadCategory, uploadCaption, currentRetailerId ?? undefined)
            const newPhoto = res.photo
            if (uploadCategory === 'gallery') {
                setGalleryPhotos(prev => [...prev, newPhoto])
            } else {
                setWinningWallPhotos(prev => [...prev, newPhoto])
            }
            setUploadDialog(false)
            setSuccess('圖片上傳成功！')
            setTimeout(() => setSuccess(''), 3000)
        } catch {
            setError('圖片上傳失敗')
        } finally {
            setUploading(false)
        }
    }

    /** 刪除圖片 */
    async function handleDeletePhoto(photoId: number, category: 'gallery' | 'winning_wall') {
        if (!confirm('確定要刪除這張圖片嗎？')) return
        try {
            await deleteStorePhoto(photoId)
            if (category === 'gallery') {
                setGalleryPhotos(prev => prev.filter(p => p.id !== photoId))
            } else {
                setWinningWallPhotos(prev => prev.filter(p => p.id !== photoId))
            }
            setSuccess('圖片已刪除')
            setTimeout(() => setSuccess(''), 3000)
        } catch {
            setError('刪除失敗')
        }
    }

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
                <CircularProgress sx={{ color: '#d4af37' }} />
            </Box>
        )
    }

    return (
        <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>
                    ✨ 專屬頁面編輯
                </Typography>
                {currentRetailerId && (
                    <Button
                        href={`/store/${currentRetailerId}`}
                        target="_blank"
                        startIcon={<OpenInNewIcon />}
                        size="small"
                        sx={{ color: '#d4af37' }}
                    >
                        預覽頁面
                    </Button>
                )}
            </Box>

            {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {/* Banner 管理 */}
            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 3 }}>
                    <Typography variant="subtitle1" fontWeight={600} mb={2}>
                        🖼️ 頁面橫幅 (Banner)
                    </Typography>
                    {bannerUrl && (
                        <Box sx={{
                            mb: 2, borderRadius: 2, overflow: 'hidden',
                            maxHeight: 200, position: 'relative',
                        }}>
                            <img
                                src={bannerUrl}
                                alt="Banner"
                                style={{ width: '100%', objectFit: 'cover', maxHeight: 200 }}
                            />
                        </Box>
                    )}
                    <input
                        ref={bannerInputRef}
                        type="file"
                        accept="image/*"
                        style={{ display: 'none' }}
                        onChange={handleBannerUpload}
                    />
                    <Button
                        variant="outlined"
                        startIcon={<AddPhotoAlternateIcon />}
                        onClick={() => bannerInputRef.current?.click()}
                        disabled={uploading}
                        sx={{
                            borderColor: 'rgba(212, 175, 55, 0.4)',
                            color: '#d4af37',
                            '&:hover': { borderColor: '#d4af37', bgcolor: 'rgba(212, 175, 55, 0.04)' },
                        }}
                    >
                        {bannerUrl ? '更換 Banner' : '上傳 Banner'}
                    </Button>
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                        建議尺寸：1200 × 400 像素
                    </Typography>
                </CardContent>
            </Card>

            {/* 店家簡介 */}
            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 3 }}>
                    <Typography variant="subtitle1" fontWeight={600} mb={2}>
                        📝 店家簡介
                    </Typography>
                    <TextField
                        fullWidth multiline rows={4}
                        placeholder="介紹您的店家特色、服務理念..."
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        sx={{ mb: 2 }}
                    />
                    <TextField
                        fullWidth
                        label="營業時間"
                        placeholder="例如：週一至週六 09:00 - 22:00，週日公休"
                        value={businessHours}
                        onChange={(e) => setBusinessHours(e.target.value)}
                    />
                </CardContent>
            </Card>

            {/* 聯絡方式 */}
            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 3 }}>
                    <Typography variant="subtitle1" fontWeight={600} mb={2}>
                        📞 聯絡方式
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            fullWidth label="電話號碼" placeholder="02-XXXX-XXXX"
                            value={contactPhone}
                            onChange={(e) => setContactPhone(e.target.value)}
                        />
                        <TextField
                            fullWidth label="LINE ID 或連結" placeholder="@xxx 或 https://line.me/..."
                            value={contactLine}
                            onChange={(e) => setContactLine(e.target.value)}
                        />
                        <TextField
                            fullWidth label="Facebook 粉專連結" placeholder="https://facebook.com/..."
                            value={contactFb}
                            onChange={(e) => setContactFb(e.target.value)}
                        />
                    </Box>
                </CardContent>
            </Card>

            {/* 中獎牆 */}
            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="subtitle1" fontWeight={600}>
                            🏆 中獎牆
                        </Typography>
                        <Chip
                            label={`${winningWallPhotos.length} / 10`}
                            size="small"
                            sx={{ bgcolor: 'rgba(212, 175, 55, 0.1)', color: '#d4af37' }}
                        />
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                        {winningWallPhotos.map((p: any) => (
                            <Box key={p.id} sx={{
                                position: 'relative', width: 120, height: 120,
                                borderRadius: 2, overflow: 'hidden',
                                border: '1px solid rgba(255,255,255,0.08)',
                            }}>
                                <img src={p.imageUrl} alt={p.caption}
                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                <IconButton
                                    size="small"
                                    onClick={() => handleDeletePhoto(p.id, 'winning_wall')}
                                    sx={{
                                        position: 'absolute', top: 2, right: 2,
                                        bgcolor: 'rgba(0,0,0,0.6)', color: '#fff',
                                        '&:hover': { bgcolor: 'rgba(239,68,68,0.8)' },
                                    }}
                                >
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                                {p.caption && (
                                    <Box sx={{
                                        position: 'absolute', bottom: 0, left: 0, right: 0,
                                        bgcolor: 'rgba(0,0,0,0.6)', p: '2px 6px',
                                        fontSize: '0.7rem', color: '#fff', textAlign: 'center',
                                    }}>
                                        {p.caption}
                                    </Box>
                                )}
                            </Box>
                        ))}
                    </Box>
                    {winningWallPhotos.length < 10 && (
                        <Button
                            variant="outlined" size="small"
                            startIcon={<AddPhotoAlternateIcon />}
                            onClick={() => openUploadDialog('winning_wall')}
                            sx={{
                                borderColor: 'rgba(212, 175, 55, 0.4)', color: '#d4af37',
                                '&:hover': { borderColor: '#d4af37' },
                            }}
                        >
                            新增中獎照片
                        </Button>
                    )}
                </CardContent>
            </Card>

            {/* 店內相簿 */}
            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="subtitle1" fontWeight={600}>
                            📸 店內相簿
                        </Typography>
                        <Chip
                            label={`${galleryPhotos.length} / 10`}
                            size="small"
                            sx={{ bgcolor: 'rgba(212, 175, 55, 0.1)', color: '#d4af37' }}
                        />
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                        {galleryPhotos.map((p: any) => (
                            <Box key={p.id} sx={{
                                position: 'relative', width: 120, height: 120,
                                borderRadius: 2, overflow: 'hidden',
                                border: '1px solid rgba(255,255,255,0.08)',
                            }}>
                                <img src={p.imageUrl} alt={p.caption}
                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                <IconButton
                                    size="small"
                                    onClick={() => handleDeletePhoto(p.id, 'gallery')}
                                    sx={{
                                        position: 'absolute', top: 2, right: 2,
                                        bgcolor: 'rgba(0,0,0,0.6)', color: '#fff',
                                        '&:hover': { bgcolor: 'rgba(239,68,68,0.8)' },
                                    }}
                                >
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </Box>
                        ))}
                    </Box>
                    {galleryPhotos.length < 10 && (
                        <Button
                            variant="outlined" size="small"
                            startIcon={<AddPhotoAlternateIcon />}
                            onClick={() => openUploadDialog('gallery')}
                            sx={{
                                borderColor: 'rgba(212, 175, 55, 0.4)', color: '#d4af37',
                                '&:hover': { borderColor: '#d4af37' },
                            }}
                        >
                            新增店內照片
                        </Button>
                    )}
                </CardContent>
            </Card>

            {/* 浮動儲存按鈕 */}
            <Box sx={{ position: 'fixed', bottom: 32, right: 32, zIndex: 1000 }}>
                <Button
                    variant="contained" size="large"
                    startIcon={<SaveIcon />}
                    onClick={handleSave}
                    disabled={saving || loading}
                    sx={{
                        background: 'linear-gradient(135deg, #d4af37, #b8962e)',
                        '&:hover': { background: 'linear-gradient(135deg, #b8962e, #96790a)' },
                        px: 4, py: 1.5, borderRadius: '30px',
                        boxShadow: '0 8px 16px rgba(212, 175, 55, 0.3)',
                        fontSize: '1.1rem', fontWeight: 600,
                    }}
                >
                    {saving ? '儲存中...' : '儲存變更'}
                </Button>
            </Box>

            {/* 上傳圖片對話框 */}
            <Dialog open={uploadDialog} onClose={() => setUploadDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>
                    {uploadCategory === 'gallery' ? '📸 新增店內照片' : '🏆 新增中獎照片'}
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                        />
                        <TextField
                            fullWidth
                            label={uploadCategory === 'winning_wall' ? '獎項名稱（選填）' : '照片說明（選填）'}
                            placeholder={uploadCategory === 'winning_wall' ? '例如：頭獎 200 萬' : '例如：寬敞的店內環境'}
                            value={uploadCaption}
                            onChange={(e) => setUploadCaption(e.target.value)}
                        />
                        <Typography variant="caption" color="text.secondary">
                            圖片會自動壓縮為 WebP 格式，單張最大 5MB。
                        </Typography>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUploadDialog(false)}>取消</Button>
                    <Button
                        onClick={handlePhotoUpload}
                        disabled={uploading}
                        variant="contained"
                        sx={{
                            bgcolor: '#d4af37',
                            '&:hover': { bgcolor: '#b8962e' },
                        }}
                    >
                        {uploading ? <CircularProgress size={20} /> : '上傳'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    )
}
