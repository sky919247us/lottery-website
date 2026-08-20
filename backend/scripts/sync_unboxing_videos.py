# -*- coding: utf-8 -*-
"""把「包本解密」播放清單的影片對應到各期開箱資料

資料先上、影片後上是常態流程，所以這支腳本是獨立可重跑的：拍片上架後跑一次，
就會把影片連結與縮圖補回對應期數的 unboxing_sessions。

對應方式：頻道的影片標題結尾一律帶 #期數（例如「… #5151 #樂刮$5,000」），
直接用正規式抓 4 位數期數即可，不需要 YouTube Data API 金鑰。

來源：YouTube 官方 RSS（免金鑰、穩定）
  https://www.youtube.com/feeds/videos.xml?playlist_id=<PLAYLIST_ID>
限制：RSS 只回最近 15 部。更舊的影片請用 --map 手動指定，例如
  --map 5121=https://youtu.be/xxxxxxxxxxx

用法：
    uv run python scripts/sync_unboxing_videos.py                 # 預覽
    uv run python scripts/sync_unboxing_videos.py --commit        # 寫入

Windows CP950 注意：摘要寫成 UTF-8 檔，不 print 中文到 stdout。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import SessionLocal, init_db  # noqa: E402
from app.model.unboxing import UnboxingSession  # noqa: E402

# 【包本解密】大樣本刮卡殘酷真相
DEFAULT_PLAYLIST = "PLBdL0u1z-6I4Kq6xqPPzREN9B45Vn5otf"

ENTRY_RE = re.compile(
    r"<entry>.*?<yt:videoId>(.*?)</yt:videoId>.*?<media:title>(.*?)</media:title>.*?</entry>",
    re.S,
)
GAME_ID_RE = re.compile(r"#(5\d{3})\b")


def unescape(s: str) -> str:
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return s


def fetch_playlist(playlist_id: str, attempts: int = 4) -> list[tuple[str, str]]:
    """抓取播放清單 RSS

    這個端點會間歇性回 404 / 500（對方端節流，非參數錯誤），故重試數次。
    另外它對瀏覽器類 User-Agent 反應不佳，用 urllib 預設 UA 即可。
    """
    url = "https://www.youtube.com/feeds/videos.xml?playlist_id=%s" % playlist_id
    last = None
    for i in range(attempts):
        try:
            xml = urllib.request.urlopen(url, timeout=25).read().decode("utf-8")
            return [(vid, unescape(title)) for vid, title in ENTRY_RE.findall(xml)]
        except Exception as e:  # noqa: BLE001
            last = e
            if i < attempts - 1:
                time.sleep(2 * (i + 1))
    raise last


def video_id_from_url(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|/embed/)([\w-]{11})", url or "")
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--playlist", default=DEFAULT_PLAYLIST)
    ap.add_argument(
        "--map",
        action="append",
        default=[],
        help="手動指定 期數=影片網址，可重複（供 RSS 15 部以外的舊片）",
    )
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--report", default="data/unboxing/_video_sync_report.txt")
    args = ap.parse_args()

    lines = ["模式：%s" % ("COMMIT" if args.commit else "DRY-RUN"), ""]

    # 期數 → (videoId, title)；同期多支影片時取播放清單中最新的那支
    mapping: dict[str, tuple[str, str]] = {}
    try:
        entries = fetch_playlist(args.playlist)
        lines.append("RSS 取得 %d 部影片" % len(entries))
        for vid, title in entries:
            m = GAME_ID_RE.search(title)
            if not m:
                lines.append("  ? 標題無期數標籤，略過：%s" % title[:50])
                continue
            gid = m.group(1)
            if gid not in mapping:
                mapping[gid] = (vid, title)
    except Exception as e:  # noqa: BLE001
        lines.append("!! RSS 取得失敗：%r" % e)

    for pair in args.map:
        if "=" not in pair:
            continue
        gid, url = pair.split("=", 1)
        vid = video_id_from_url(url)
        if vid:
            mapping[gid.strip()] = (vid, "（手動指定）")
            lines.append("  手動指定 %s -> %s" % (gid.strip(), vid))

    init_db()
    db = SessionLocal()
    updated, missing = 0, []
    try:
        sessions = db.query(UnboxingSession).all()
        by_game: dict[str, list[UnboxingSession]] = {}
        for s in sessions:
            by_game.setdefault(s.gameId, []).append(s)

        lines.append("")
        for gid, sess_list in sorted(by_game.items(), reverse=True):
            hit = mapping.get(gid)
            if not hit:
                missing.append(gid)
                lines.append("=== %s：播放清單中找不到對應影片（資料先上，之後再跑一次即可）" % gid)
                continue
            vid, title = hit
            for s in sess_list:
                s.videoId = vid
                s.videoUrl = "https://www.youtube.com/watch?v=%s" % vid
                s.videoTitle = title
                updated += 1
            lines.append("=== %s：%s\n    %s" % (gid, vid, title[:80]))

        if args.commit:
            db.commit()
            lines.append("\n已寫入 %d 個場次。" % updated)
        else:
            db.rollback()
            lines.append("\nDRY-RUN，未寫入（會影響 %d 個場次）。" % updated)
        if missing:
            lines.append("尚無影片的期數：%s" % ", ".join(missing))
    finally:
        db.close()

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print("video sync done updated=%d missing=%d commit=%s" % (updated, len(missing), args.commit))


if __name__ == "__main__":
    main()
