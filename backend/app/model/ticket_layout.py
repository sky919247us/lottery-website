# -*- coding: utf-8 -*-
"""面額 → 每本張數對照（無任何相依，避免與 database.py 的模型 import 形成循環）

與 frontend/src/utils/scratchcard.ts 同步維護。
資料來源：使用者提供的實務對照，並與 frontend/src/pages/Detail.tsx 既有的
PRICE_TO_TICKETS_PER_BOOK 核對一致。
"""

PRICE_TO_TICKETS_PER_BOOK = {
    100: 100,
    200: 100,
    300: 100,
    500: 50,
    1000: 25,
    2000: 19,
}


def default_tickets_per_book(price):
    """依面額取得每本張數，未知面額回 100"""
    try:
        return PRICE_TO_TICKETS_PER_BOOK.get(int(price or 0), 100)
    except (TypeError, ValueError):
        return 100
