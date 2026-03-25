"""
LINE Messaging API 通知服務
用於商家審核結果通知與 PRO 到期提醒
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")


def _send(line_user_id: str, messages: list[dict]) -> bool:
    """發送 LINE 訊息"""
    if not LINE_TOKEN:
        logger.warning("[LINE] 未設定 LINE_CHANNEL_ACCESS_TOKEN，跳過通知")
        return False
    if not line_user_id:
        logger.warning("[LINE] lineUserId 為空，跳過通知")
        return False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    payload = {
        "to": line_user_id,
        "messages": messages,
    }

    try:
        res = requests.post(LINE_API_URL, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"[LINE] ✅ 通知已送出 → {line_user_id}")
            return True
        else:
            logger.error(f"[LINE] ❌ 發送失敗: {res.status_code} {res.text}")
            return False
    except Exception as e:
        logger.error(f"[LINE] ❌ 發送例外: {e}")
        return False


def notify_claim_approved(
    line_user_id: str, store_name: str, claim_id: int,
    username: str | None = None, password: str | None = None,
) -> bool:
    """審核通過通知（含後台帳密）"""
    # 帳密資訊區塊
    credential_contents = []
    if username and password:
        credential_contents = [
            {
                "type": "separator",
                "margin": "lg",
            },
            {
                "type": "text",
                "text": "🔐 商家後台帳號",
                "weight": "bold",
                "size": "sm",
                "margin": "lg",
            },
            {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "spacing": "sm",
                "backgroundColor": "#f5f5f5",
                "cornerRadius": "md",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "text",
                        "text": f"帳號：{username}",
                        "size": "sm",
                        "weight": "bold",
                    },
                    {
                        "type": "text",
                        "text": f"密碼：{password}",
                        "size": "sm",
                        "weight": "bold",
                    },
                ],
            },
            {
                "type": "text",
                "text": "⚠️ 請妥善保管密碼，建議登入後修改",
                "size": "xxs",
                "color": "#ef4444",
                "margin": "md",
                "wrap": True,
            },
        ]

    messages = [
        {
            "type": "flex",
            "altText": f"🎉 [{store_name}] 認領申請已通過！",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "✅ 認領申請通過",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#ffffff",
                        }
                    ],
                    "backgroundColor": "#22c55e",
                    "paddingAll": "16px",
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"恭喜！您的「{store_name}」認領申請已通過審核。",
                            "wrap": True,
                            "size": "md",
                        },
                        {
                            "type": "text",
                            "text": "您現在可以登入商家後台管理店家資訊。",
                            "wrap": True,
                            "size": "sm",
                            "color": "#666666",
                        },
                    ] + credential_contents,
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "登入商家後台",
                                "uri": "https://i168.win/admin/",
                            },
                            "style": "primary",
                            "color": "#0B192C",
                        }
                    ],
                },
            },
        }
    ]
    return _send(line_user_id, messages)


def notify_claim_rejected(line_user_id: str, store_name: str, reason: str) -> bool:
    """審核拒絕通知"""
    reason_text = reason if reason else "請確認上傳的證件是否清晰完整"
    messages = [
        {
            "type": "flex",
            "altText": f"[{store_name}] 認領申請需補件",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "❌ 認領申請未通過",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#ffffff",
                        }
                    ],
                    "backgroundColor": "#ef4444",
                    "paddingAll": "16px",
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"「{store_name}」的認領申請未通過。",
                            "wrap": True,
                            "size": "md",
                        },
                        {
                            "type": "text",
                            "text": f"原因：{reason_text}",
                            "wrap": True,
                            "size": "sm",
                            "color": "#ef4444",
                        },
                        {
                            "type": "text",
                            "text": "您可以重新提交申請。",
                            "wrap": True,
                            "size": "sm",
                            "color": "#666666",
                        },
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "重新申請",
                                "uri": "https://i168.win/merchant",
                            },
                            "style": "primary",
                            "color": "#0B192C",
                        }
                    ],
                },
            },
        }
    ]
    return _send(line_user_id, messages)


def notify_pro_expiring(line_user_id: str, store_name: str, days_left: int, expires_date: str) -> bool:
    """PRO 即將到期提醒"""
    messages = [
        {
            "type": "flex",
            "altText": f"⚠️ [{store_name}] PRO 方案即將到期（剩 {days_left} 天）",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"⚠️ PRO 方案剩 {days_left} 天到期",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#ffffff",
                        }
                    ],
                    "backgroundColor": "#f59e0b",
                    "paddingAll": "16px",
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"「{store_name}」的 PRO 方案將於 {expires_date} 到期。",
                            "wrap": True,
                            "size": "md",
                        },
                        {
                            "type": "text",
                            "text": "續訂後可繼續享有專業頁面、中獎牆等 PRO 功能。",
                            "wrap": True,
                            "size": "sm",
                            "color": "#666666",
                        },
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "立即續訂 PRO",
                                "uri": "https://i168.win/merchant",
                            },
                            "style": "primary",
                            "color": "#d4af37",
                        }
                    ],
                },
            },
        }
    ]
    return _send(line_user_id, messages)
