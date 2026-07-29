"""Pulse M1 冒烟测试 —— 运行追踪器 15 秒后验证数据写入."""

import sys
import time
from datetime import date
from pathlib import Path

# 确保可以从项目根目录 import
sys.path.insert(0, str(Path(__file__).parent.parent))

# 修复 Windows 终端 GBK 编码问题
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pulse.core.tracker import AppTracker, TrackerConfig
from pulse.db.repository import Repository
from pulse.utils.constants import DB_PATH


def smoke_test():
    print("=" * 50)
    print("Pulse M1 冒烟测试")
    print(f"数据库路径: {DB_PATH}")
    print("=" * 50)

    # 清理旧的测试数据库
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("已清理旧数据库")

    # 初始化
    repo = Repository(str(DB_PATH))
    repo.initialize_db()
    print("数据库已初始化\n")

    tracker = AppTracker(TrackerConfig(poll_interval=1.0, idle_threshold=300), repo)

    # 注册回调
    flushed = []

    def on_flush(session):
        flushed.append(session)
        mins = session.duration_seconds // 60
        secs = session.duration_seconds % 60
        print(f"  [会话结束] {session.process_name:<20}  {mins:>3}分{secs:>2}秒"
              f"  |  {session.window_title or '(无标题)'}")

    tracker.on_session_flushed = on_flush

    # 启动追踪器
    tracker.start()

    print("\n追踪器已启动，等待 15 秒...")
    print("在此期间请切换一下窗口（如记事本、浏览器等）以触发多段会话\n")

    for i in range(15, 0, -1):
        print(f"\r  倒计时: {i:>2}s  |  当前: {tracker.current_session.process_name if tracker.current_session else 'N/A'}"
              f"  ({tracker.current_session.duration_seconds if tracker.current_session else 0}s)", end="")
        time.sleep(1)

    print("\n")
    tracker.stop()

    # 验证结果
    print("\n" + "=" * 50)
    print("验证结果")
    print("=" * 50)

    today = date.today()
    total_sec = repo.get_total_duration_by_date(today)
    record_count = len(repo.get_sessions_by_date(today))

    print(f"  今日总活跃时长: {total_sec // 60} 分 {total_sec % 60} 秒")
    print(f"  数据库会话记录数: {record_count}")
    print(f"  本次运行刷新会话数: {len(flushed)}")

    if total_sec > 0 and record_count > 0:
        print("\n  Top 应用:")
        for app in repo.get_usage_summary_by_date(today, "process_name"):
            mins = app["total_seconds"] // 60
            secs = app["total_seconds"] % 60
            print(f"    {app['name']:<20}  {mins:>3}分{secs:>2}秒")
    else:
        print("\n  [!!] 无数据记录！")
        return False

    # 检查数据库文件
    db_size = DB_PATH.stat().st_size
    print(f"\n  数据库文件大小: {db_size:,} 字节")
    print(f"  测试 {'[OK] 通过' if record_count > 0 else '[FAIL] 失败'}")
    return record_count > 0


if __name__ == "__main__":
    success = smoke_test()
    sys.exit(0 if success else 1)
