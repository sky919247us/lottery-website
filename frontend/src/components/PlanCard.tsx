/**
 * 商家方案卡片
 * 顯示：FREE / PRO 狀態、審核進度、升級按鈕、到期日期
 */

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Crown, Clock, CheckCircle, AlertCircle, Zap } from 'lucide-react'
import './PlanCard.css'

interface PlanCardProps {
    claimId: number | null
    retailerId: number
    userId: number
}

interface ClaimStatus {
    id: number
    status: 'pending' | 'approved' | 'rejected'
    tier: 'basic' | 'pro'
    verificationComplete: boolean
    paymentStatus: 'pending' | 'paid'
    proExpiresAt: string | null
}

export default function PlanCard({ claimId, retailerId, userId }: PlanCardProps) {
    const [claim, setClaim] = useState<ClaimStatus | null>(null)
    const [loading, setLoading] = useState(false)
    const [checkoutUrl, setCheckoutUrl] = useState('')

    // 取得申請狀態
    useEffect(() => {
        if (!claimId) return

        setLoading(true)
        fetch(`/api/merchant/claim/${claimId}/status`)
            .then(r => r.json())
            .then(setClaim)
            .catch(() => setClaim(null))
            .finally(() => setLoading(false))
    }, [claimId])

    // 取得結帳 URL
    const fetchCheckoutUrl = async () => {
        if (!claimId) return

        try {
            const res = await fetch(`/api/merchant/claim/${claimId}/checkout-url`)
            const data = await res.json()
            if (data.checkoutUrl) {
                setCheckoutUrl(data.checkoutUrl)
                // 跳轉到 Lemonsqueezy
                window.location.href = data.checkoutUrl
            }
        } catch (err) {
            console.error('取得結帳連結失敗:', err)
        }
    }

    if (!claimId) {
        // 未認領
        return (
            <motion.div
                className="plan-card glass-card"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="plan-card__header">
                    <h3>💰 我的方案</h3>
                </div>
                <div className="plan-card__content">
                    <p className="plan-card__status">尚未認領店家</p>
                    <p className="plan-card__desc">認領店家後即可查看方案詳情與升級選項</p>
                </div>
            </motion.div>
        )
    }

    if (loading) {
        return (
            <motion.div
                className="plan-card glass-card"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="plan-card__spinner" />
                <p>載入方案資訊中...</p>
            </motion.div>
        )
    }

    if (!claim) {
        return null
    }

    // 尚未核准
    if (claim.status === 'pending') {
        return (
            <motion.div
                className="plan-card glass-card plan-card--pending"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="plan-card__header">
                    <h3>💰 我的方案</h3>
                    <span className="plan-card__badge badge--pending">審核中</span>
                </div>
                <div className="plan-card__content">
                    <div className="plan-card__status-item">
                        <Clock size={16} />
                        <p>您的認領申請正在審核中</p>
                    </div>
                    <p className="plan-card__desc">審核通過後即可升級至 PRO 方案，享受專業商家功能</p>
                </div>
            </motion.div>
        )
    }

    // 已駁回
    if (claim.status === 'rejected') {
        return (
            <motion.div
                className="plan-card glass-card plan-card--rejected"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="plan-card__header">
                    <h3>💰 我的方案</h3>
                    <span className="plan-card__badge badge--rejected">已駁回</span>
                </div>
                <div className="plan-card__content">
                    <div className="plan-card__status-item">
                        <AlertCircle size={16} />
                        <p>申請已被駁回</p>
                    </div>
                </div>
            </motion.div>
        )
    }

    // 已核准 - 顯示升級或已是 PRO
    return (
        <motion.div
            className={`plan-card glass-card plan-card--${claim.tier}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
        >
            <div className="plan-card__header">
                <h3>
                    {claim.tier === 'pro' ? <Crown size={20} /> : '💰'}
                    我的方案
                </h3>
                <span className={`plan-card__badge badge--${claim.tier}`}>
                    {claim.tier === 'pro' ? 'PRO 方案' : 'FREE 方案'}
                </span>
            </div>

            <div className="plan-card__content">
                {claim.tier === 'basic' && claim.status === 'approved' && (
                    <>
                        <p className="plan-card__desc">
                            您已通過審核！升級至 PRO 方案可享受：
                        </p>
                        <ul className="plan-card__features">
                            <li>✨ 專業商家頁面設計</li>
                            <li>📸 中獎打卡牆展示</li>
                            <li>📊 數據分析儀表板</li>
                            <li>🎯 優先搜尋排名</li>
                        </ul>
                        <button
                            className="plan-card__upgrade-btn"
                            onClick={fetchCheckoutUrl}
                            disabled={loading}
                        >
                            <Zap size={16} /> 立即升級 PRO — NT$1,680/年
                        </button>
                    </>
                )}

                {claim.tier === 'pro' && (
                    <>
                        <div className="plan-card__pro-status">
                            <CheckCircle size={18} />
                            <p>已啟用 PRO 方案</p>
                        </div>
                        {claim.proExpiresAt && (
                            <p className="plan-card__expires">
                                📅 到期日期：{new Date(claim.proExpiresAt).toLocaleDateString('zh-TW')}
                            </p>
                        )}
                        {claim.paymentStatus === 'paid' && (
                            <p className="plan-card__payment-status">✅ 已完成付款</p>
                        )}
                    </>
                )}
            </div>
        </motion.div>
    )
}
