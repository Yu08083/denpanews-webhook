"""
GitHub Actions から呼ばれるエントリポイント。

- 通常モード: scraper.py を1回だけ実行
- 集中監視モード: 環境変数 INTENSIVE=1 のとき、JSTの 10:59-11:02 / 14:59-15:02 の
  該当時刻になるまで待機しつつ、1分間隔で計4回 scraper.py を実行する
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# 監視ウィンドウ (start, end の各分を含む) JST
INTENSIVE_WINDOWS = [
    (10, 59, 11, 2),  # 10:59, 11:00, 11:01, 11:02 の4回
    (14, 59, 15, 2),  # 14:59, 15:00, 15:01, 15:02 の4回
]


def run_scraper():
    print(f"[{datetime.now(JST).strftime('%H:%M:%S JST')}] scraper 実行")
    res = subprocess.run([sys.executable, "scraper.py"])
    if res.returncode != 0:
        print(f"  scraper 終了コード: {res.returncode}", file=sys.stderr)


def expected_minutes_in_window(now: datetime):
    """現在時刻が監視ウィンドウ内なら、その日のウィンドウの実行予定時刻リストを返す。
    そうでなければ None。
    """
    for sh, sm, eh, em in INTENSIVE_WINDOWS:
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=59, microsecond=0)
        if start <= now <= end:
            slots = []
            t = start
            while t <= end.replace(second=0):
                slots.append(t)
                t += timedelta(minutes=1)
            return slots
    return None


def upcoming_window(now: datetime, max_wait_minutes: int = 10):
    """近い将来 (max_wait_minutes 分以内) に始まる監視ウィンドウがあれば、
    そのスロット一覧を返す。なければ None。
    """
    for sh, sm, eh, em in INTENSIVE_WINDOWS:
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=59, microsecond=0)
        if now < start and (start - now).total_seconds() <= max_wait_minutes * 60:
            slots = []
            t = start
            while t <= end.replace(second=0):
                slots.append(t)
                t += timedelta(minutes=1)
            return slots
    return None


def intensive_mode():
    now = datetime.now(JST)
    slots = expected_minutes_in_window(now) or upcoming_window(now)
    if not slots:
        print(f"[{now.strftime('%H:%M JST')}] 集中監視時間外。1回だけ実行します。")
        run_scraper()
        return

    print(f"[{now.strftime('%H:%M JST')}] 集中監視モード開始。実行予定: "
          f"{[s.strftime('%H:%M') for s in slots]}")

    for slot in slots:
        # スロット時刻まで待機 (既に過ぎていればすぐ実行)
        now = datetime.now(JST)
        wait = (slot - now).total_seconds()
        if wait > 0:
            print(f"  → {slot.strftime('%H:%M:00')} まで {wait:.0f}秒待機")
            time.sleep(wait)
        run_scraper()


def main():
    if os.environ.get("INTENSIVE") == "1":
        intensive_mode()
    else:
        run_scraper()


if __name__ == "__main__":
    main()
