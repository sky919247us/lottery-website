/**
 * 影片列表頁面
 * 依頻道播放清單分類，6 個主題區域
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, ChevronDown, ExternalLink, Lock } from 'lucide-react'
import SeoHead from '../components/SeoHead'
import './Videos.css'

/** 頻道資訊 */
const CHANNEL_URL = 'https://www.youtube.com/channel/UCU68swgh6cL3cCauKf5ZJKA'

/** 播放清單分類定義 */
interface PlaylistCategory {
    id: string
    emoji: string
    title: string
    subtitle: string
    description: string
    /** YouTube 播放清單 ID（嵌入用） */
    playlistId: string
    /** 是否為會員限定 */
    isMemberOnly?: boolean
    /** 標籤色 */
    tagColor: string
}

const PLAYLISTS: PlaylistCategory[] = [
    {
        id: 'new-review',
        emoji: '🔬',
        title: '【新品實測】社長開箱與數據健檢',
        subtitle: '新品實測',
        description: '很多人進彩券行都是憑感覺在挑，但是身為研究室的社長，我們只講數據！每當有新款刮刮樂上市，社長會第一時間對比官方宣傳與真實數據的反差。我們用期望值與賺錢率幫大家健檢，揪出哪些卡水很深，幫助各位研究員避開地雷。',
        playlistId: 'PLBdL0u1z-6I5Psfqk72nmPKhZ_UESHDK-',
        tagColor: '#1E8449',
    },
    {
        id: 'street-test',
        emoji: '🎪',
        title: '【街頭實戰】對抗機率的實體實驗',
        subtitle: '街頭實戰',
        description: '我們將刮刮樂視為一場對抗機率的實驗！這系列社長會走出研究室，親自在彩券行實測刮卡。究竟實測結果會驗證我們研究室的表格數據，還是社長今天單純出門做公益？話不多說，社長直接刮給你看看最真實的戰況！',
        playlistId: 'PLBdL0u1z-6I5hRRkxaZEsPcPZj78no2Jj',
        tagColor: '#F39C12',
    },
    {
        id: 'full-book',
        emoji: '📊',
        title: '【包本解密】大樣本刮卡殘酷真相',
        subtitle: '包本解密',
        description: '買一整本到底會不會賺？數據不會騙人！本系列為各位研究員帶來「整本」的大樣本數據分析。社長直接帶你攤開一整本的完整戰績，算給你看整本的地板跟天花板在哪裡，直接揭穿假中獎的陷阱。想看更多大數據實測的朋友，加入我們的研究行列！',
        playlistId: 'PLBdL0u1z-6I4Kq6xqPPzREN9B45Vn5otf',
        tagColor: '#D32F2F',
    },
    {
        id: 'bingo',
        emoji: '🎱',
        title: '【賓果專區】五分鐘一局的數學課',
        subtitle: '賓果專區',
        description: '除了刮刮樂，BINGO BINGO 同樣需要精密的數據檢驗！這系列社長將利用數學期望值破解電腦彩券的迷思。不管你習慣玩幾星，我們用最理性的態度幫你剖析機率，不鼓勵盲目賭博，強調量力而為。',
        playlistId: 'PLBdL0u1z-6I76NNI4LGcwZuZh2rIq1QpE',
        tagColor: '#8E44AD',
    },
    {
        id: 'knowledge',
        emoji: '📚',
        title: '【研究員必修】刮刮樂防雷與機率科普',
        subtitle: '研究員必修',
        description: '想加入研究室，這份終極防雷指南必看！這系列專門講解核心的數據定義，帶你搞懂「期望值」、「回本率」與「賺錢率」到底差在哪。社長教你怎麼看懂背後的數學邏輯，建立將刮刮樂視為娛樂而非投資的正確觀念。',
        playlistId: 'PLBdL0u1z-6I4ZX4XHaTaZVugQbMlYfKhb',
        tagColor: '#0B192C',
    },
    {
        id: 'member',
        emoji: '🔒',
        title: '【刮刮研究室】會員限定：機密數據庫 & 審計原始檔',
        subtitle: '會員限定',
        description: '這裡是刮刮研究室的「軍火庫」。存放所有未經剪輯的實測過程、獨家審計報告，以及公開頻道看不到的殘酷真相。這裡沒有特效，沒有綜藝濾鏡，只有最冰冷的數據與機率。',
        playlistId: 'PLBdL0u1z-6I52MSrlCT0UZqz7iUwatqLH',
        isMemberOnly: true,
        tagColor: '#5A6268',
    },
]

export default function Videos() {
    /** 展開 / 收合播放清單 */
    const [expandedId, setExpandedId] = useState<string | null>(PLAYLISTS[0].id)
    /** 目前播放的清單 */
    const [playingId, setPlayingId] = useState<string | null>(null)

    function toggleExpand(id: string) {
        setExpandedId(prev => prev === id ? null : id)
    }

    function handlePlay(playlist: PlaylistCategory) {
        if (playlist.isMemberOnly) {
            // NOTE: 會員限定導向 YouTube 會員頁
            window.open(`${CHANNEL_URL}/join`, '_blank')
            return
        }
        setPlayingId(playlist.id)
        setExpandedId(playlist.id)
    }

    return (
        <div className="videos container">
            <SeoHead
                title="影片列表 — 刮刮研究室開箱與數據分析"
                description="刮刮研究室精選影片，新品實測、街頭實戰、包本解密、賓果專區、機率科普，用數據破解刮刮樂。"
                path="/videos"
            />
            {/* 頁面標題 */}
            <motion.div
                className="videos__page-header"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <h1 className="videos__page-title">📺 影片列表</h1>
                <p className="videos__page-desc">
                    刮刮研究室精選影片，依主題分類瀏覽
                </p>
                <a
                    href={CHANNEL_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="videos__yt-btn"
                >
                    <Play size={16} />
                    前往 YouTube 頻道
                    <ExternalLink size={14} />
                </a>
            </motion.div>

            {/* 播放清單分類 */}
            <div className="videos__playlists">
                {PLAYLISTS.map((pl, index) => {
                    const isExpanded = expandedId === pl.id
                    const isPlaying = playingId === pl.id

                    return (
                        <motion.div
                            key={pl.id}
                            className={`playlist-card ${isExpanded ? 'playlist-card--expanded' : ''} ${pl.isMemberOnly ? 'playlist-card--member' : ''}`}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.06 }}
                        >
                            {/* 清單標頭 — 點擊展開/收合 */}
                            <button
                                className="playlist-card__header"
                                onClick={() => toggleExpand(pl.id)}
                            >
                                <div className="playlist-card__tag" style={{ background: pl.tagColor }}>
                                    <span>{pl.emoji}</span>
                                    <span>{pl.subtitle}</span>
                                </div>
                                <h2 className="playlist-card__title">{pl.title}</h2>
                                <ChevronDown
                                    size={20}
                                    className={`playlist-card__chevron ${isExpanded ? 'playlist-card__chevron--open' : ''}`}
                                />
                            </button>

                            {/* 展開的內容 */}
                            <AnimatePresence>
                                {isExpanded && (
                                    <motion.div
                                        className="playlist-card__body"
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: 'auto', opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{ duration: 0.3 }}
                                    >
                                        <p className="playlist-card__desc">{pl.description}</p>

                                        {pl.isMemberOnly && (
                                            <div className="playlist-card__member-notice">
                                                <Lock size={16} />
                                                <span>本區內容僅供「研究員」級別以上會員觀看，請勿外流。</span>
                                            </div>
                                        )}

                                        {/* 播放按鈕 */}
                                        <div className="playlist-card__actions">
                                            <button
                                                className={`playlist-card__play-btn ${pl.isMemberOnly ? 'playlist-card__play-btn--member' : ''}`}
                                                onClick={() => handlePlay(pl)}
                                            >
                                                {pl.isMemberOnly ? (
                                                    <>
                                                        <Lock size={16} />
                                                        加入會員觀看
                                                    </>
                                                ) : (
                                                    <>
                                                        <Play size={16} />
                                                        {isPlaying ? '正在播放' : '播放此清單'}
                                                    </>
                                                )}
                                            </button>
                                            {!pl.isMemberOnly && (
                                                <a
                                                    href={`https://www.youtube.com/playlist?list=${pl.playlistId}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="playlist-card__yt-link"
                                                >
                                                    在 YouTube 觀看
                                                    <ExternalLink size={14} />
                                                </a>
                                            )}
                                        </div>

                                        {/* 嵌入式播放器 */}
                                        {isPlaying && !pl.isMemberOnly && (
                                            <motion.div
                                                className="playlist-card__player"
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                transition={{ duration: 0.3 }}
                                            >
                                                <iframe
                                                    className="playlist-card__iframe"
                                                    src={`https://www.youtube.com/embed/videoseries?list=${pl.playlistId}`}
                                                    title={pl.title}
                                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                                    allowFullScreen
                                                />
                                            </motion.div>
                                        )}
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>
                    )
                })}
            </div>
        </div>
    )
}
