"""数据访问层 —— 封装所有数据库操作."""

import logging
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session as SASession, sessionmaker

from pulse.db.models import Base, AppSession, AppCategory, Category, CalendarTask, CalendarTaskField, CalendarComment
from pulse.utils.constants import DB_PATH, DEFAULT_CATEGORIES

logger = logging.getLogger(__name__)


class Repository:
    """统一数据访问入口."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self._Session = sessionmaker(bind=self._engine, expire_on_commit=False)

    def initialize_db(self) -> None:
        """创建所有表并写入默认分类."""
        Base.metadata.create_all(self._engine)
        self._migrate()
        self._seed_default_categories()
        logger.info("数据库初始化完成")

    def _migrate(self) -> None:
        """增量迁移：为已有表补充新列."""
        with self.session() as s:
            # 检查 app_sessions 是否有 executable_path 列
            from sqlalchemy import inspect
            inspector = inspect(self._engine)
            columns = {c["name"] for c in inspector.get_columns("app_sessions")}
            if "executable_path" not in columns:
                s.execute(text("ALTER TABLE app_sessions ADD COLUMN executable_path VARCHAR(1024)"))
                logger.info("迁移: app_sessions 添加 executable_path 列")

            # 检查 calendar_tasks 是否有 end_date 列
            cal_cols = {c["name"] for c in inspector.get_columns("calendar_tasks")} if "calendar_tasks" in {t.name for t in Base.metadata.sorted_tables} else set()
            if cal_cols and "end_date" not in cal_cols:
                s.execute(text("ALTER TABLE calendar_tasks ADD COLUMN end_date DATE"))
                logger.info("迁移: calendar_tasks 添加 end_date 列")


    def _seed_default_categories(self) -> None:
        with self.session() as session:
            existing = session.query(Category).count()
            if existing > 0:
                return
            for i, cat in enumerate(DEFAULT_CATEGORIES):
                session.add(Category(
                    name=cat["name"],
                    color=cat["color"],
                    icon=cat["icon"],
                    is_system=True,
                    sort_order=i,
                ))

    @contextmanager
    def session(self) -> SASession:
        """获取数据库会话（上下文管理器，自动提交/回滚）.用 yield 而不是 return —— 这是 contextmanager 的标准写法。"""
        s = self._Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ─── AppSession ─────────────────────────────────────────────

    def save_session(self, session_obj: AppSession) -> AppSession:
        """保存单条使用记录."""
        with self.session() as s:
            s.add(session_obj)
            s.flush()
            return session_obj

    def get_sessions_by_date(
        self, target_date: date, offset: int = 0, limit: int = 1000
    ) -> List[AppSession]:
        """获取指定日期的所有使用记录."""
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        with self.session() as s:
            return (
                s.query(AppSession)
                .filter(AppSession.start_time >= start, AppSession.start_time < end)
                .order_by(AppSession.start_time.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

    def get_latest_session(self) -> Optional[AppSession]:
        """获取最近一条使用记录."""
        with self.session() as s:
            return s.query(AppSession).order_by(AppSession.id.desc()).first()

    def get_total_duration_by_date(
        self, target_date: date, exclude_idle: bool = True
    ) -> int:
        """获取指定日期总使用时长（秒）."""
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        with self.session() as s:
            query = s.query(func.sum(AppSession.duration_seconds)).filter(
                AppSession.start_time >= start,
                AppSession.start_time < end,
            )
            if exclude_idle:
                query = query.filter(AppSession.is_idle == False)
            result = query.scalar()
            return result or 0

    def get_usage_summary_by_date(
        self, target_date: date, group_by: str = "process_name"
    ) -> List[dict]:
        """按指定字段分组统计当日使用情况."""
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        column = getattr(AppSession, group_by, AppSession.process_name)

        with self.session() as s:
            rows = (
                s.query(
                    column,
                    func.sum(AppSession.duration_seconds).label("total_seconds"),
                )
                .filter(
                    AppSession.start_time >= start,
                    AppSession.start_time < end,
                    AppSession.is_idle == False,
                )
                .group_by(column)
                .order_by(func.sum(AppSession.duration_seconds).desc())
                .all()
            )
            return [{"name": r[0] or "未知", "total_seconds": int(r[1])} for r in rows]

    def delete_sessions_before(self, cutoff: datetime) -> int:
        """删除指定时间之前的记录."""
        with self.session() as s:
            count = s.query(AppSession).filter(AppSession.start_time < cutoff).delete()
            return count

    def get_hourly_breakdown(self, target_date: date) -> list[dict]:
        """获取指定日期每小时的使用时长（秒）."""
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        with self.session() as s:
            rows = (
                s.query(
                    func.strftime("%H", AppSession.start_time).label("hour"),
                    func.sum(AppSession.duration_seconds).label("total_seconds"),
                )
                .filter(
                    AppSession.start_time >= start,
                    AppSession.start_time < end,
                    AppSession.is_idle == False,
                )
                .group_by("hour")
                .order_by("hour")
                .all()
            )
            result = {int(r[0]): int(r[1]) for r in rows}
            return [{"hour": h, "total_seconds": result.get(h, 0)} for h in range(24)]

    def get_daily_summaries(self, start_date: date, num_days: int) -> list[dict]:
        """获取连续多天每天的总使用时长."""
        summaries = []
        for i in range(num_days):
            d = start_date + timedelta(days=i)
            total = self.get_total_duration_by_date(d)
            summaries.append({"date": d, "total_seconds": total})
        return summaries

    def get_daily_totals_for_month(self, year: int, month: int) -> list[dict]:
        """获取某月每天的总使用时长."""
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        first = date(year, month, 1)
        return self.get_daily_summaries(first, last_day)

    def get_latest_exe_path(self, process_name: str) -> Optional[str]:
        """获取某个进程名最近一条记录的可执行文件路径."""
        with self.session() as s:
            row = (
                s.query(AppSession.executable_path)
                .filter(AppSession.process_name == process_name, AppSession.executable_path.isnot(None))
                .order_by(AppSession.id.desc())
                .first()
            )
            return row[0] if row else None

    def cleanup_old_data(self, retention_days: int = 180) -> int:
        """删除 retention_days 天之前的原始会话记录."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        count = self.delete_sessions_before(cutoff)
        if count:
            logger.info("清理了 %d 条 %d 天前的过期数据", count, retention_days)
        return count

    def cleanup_by_months(self, retention_months: int) -> int:
        """删除 retention_months 个月之前的原始会话记录."""
        cutoff = datetime.now() - timedelta(days=retention_months * 30)
        count = self.delete_sessions_before(cutoff)
        if count:
            logger.info("清理了 %d 条 %d 个月前的过期数据", count, retention_months)
        return count

    # ─── Category ───────────────────────────────────────────────

    def get_all_categories(self) -> List[Category]:
        with self.session() as s:
            return s.query(Category).order_by(Category.sort_order).all()

    def get_category_by_name(self, name: str) -> Optional[Category]:
        with self.session() as s:
            return s.query(Category).filter(Category.name == name).first()

    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        with self.session() as s:
            return s.query(Category).filter(Category.id == category_id).first()

    def create_category(self, name: str, color: str = "#9E9E9E", icon: str = "📁", is_system: bool = False) -> Category:
        """创建新分类."""
        with self.session() as s:
            existing = s.query(Category).filter(Category.name == name).first()
            if existing:
                return existing
            max_order = s.query(func.max(Category.sort_order)).scalar() or 0
            cat = Category(name=name, color=color, icon=icon, is_system=is_system, sort_order=max_order + 1)
            s.add(cat)
            s.flush()
            return cat

    def delete_category(self, category_id: int) -> bool:
        """删除分类及关联的 AppCategory 映射."""
        with self.session() as s:
            s.query(AppCategory).filter(AppCategory.category_id == category_id).delete()
            count = s.query(Category).filter(Category.id == category_id).delete()
            return count > 0

    # ─── AppCategory ───────────────────────────────────────────

    def save_app_category(self, process_name: str, category_id: int, is_auto: bool = False) -> AppCategory:
        """设置应用的分类映射（upsert）. """
        with self.session() as s:
            existing = s.query(AppCategory).filter(AppCategory.process_name == process_name).first()
            if existing:
                existing.category_id = category_id
                existing.is_auto = is_auto
                obj = existing
            else:
                obj = AppCategory(process_name=process_name, category_id=category_id, is_auto=is_auto)
                s.add(obj)
            s.flush()
            return obj

    def get_app_category(self, process_name: str) -> Optional[AppCategory]:
        """获取某应用的分类映射."""
        with self.session() as s:
            return s.query(AppCategory).filter(AppCategory.process_name == process_name).first()

    def get_all_app_categories(self) -> list:
        """获取所有应用分类映射（含分类信息）. """
        with self.session() as s:
            rows = (
                s.query(AppCategory, Category)
                .join(Category, AppCategory.category_id == Category.id)
                .order_by(AppCategory.process_name)
                .all()
            )
            return [
                {
                    "process_name": ac.process_name,
                    "category_id": ac.category_id,
                    "category_name": cat.name,
                    "category_color": cat.color,
                    "is_auto": ac.is_auto,
                }
                for ac, cat in rows
            ]

    def delete_app_category(self, process_name: str) -> bool:
        """删除某应用的分类映射."""
        with self.session() as s:
            count = s.query(AppCategory).filter(AppCategory.process_name == process_name).delete()
            return count > 0

    def get_unclassified_processes(self) -> list[str]:
        """获取所有会话中出现过但尚未分类的进程名."""
        with self.session() as s:
            classified = {r[0] for r in s.query(AppCategory.process_name).all()}
            all_processes = [
                r[0] for r in s.query(AppSession.process_name)
                .filter(AppSession.is_idle == False)
                .distinct().all()
            ]
            return [p for p in all_processes if p not in classified]

    # ─── Calendar ─────────────────────────────────────────────

    def get_tasks_by_month(self, year: int, month: int) -> List:
        """获取与某月有交集的所有任务（含跨月任务）.

        筛选条件：任务开始日期 ≤ 月末，且（无结束日期 或 结束日期 ≥ 月初）
        """
        with self.session() as s:
            from sqlalchemy import func as _f, or_
            first = date(year, month, 1)
            from calendar import monthrange
            _, last_day = monthrange(year, month)
            last = date(year, month, last_day)
            rows = (
                s.query(
                    CalendarTask,
                    _f.count(func.distinct(CalendarTaskField.id)).label("field_count"),
                    _f.count(func.distinct(CalendarComment.id)).label("comment_count"),
                )
                .outerjoin(CalendarTaskField, CalendarTaskField.task_id == CalendarTask.id)
                .outerjoin(CalendarComment, CalendarComment.task_id == CalendarTask.id)
                .filter(
                    CalendarTask.date <= last,
                    or_(CalendarTask.end_date.is_(None), CalendarTask.end_date >= first),
                )
                .group_by(CalendarTask.id)
                .order_by(CalendarTask.date, CalendarTask.sort_order)
                .all()
            )
            return rows

    def get_tasks_by_date(self, target_date: date) -> List[CalendarTask]:
        """获取指定日期的所有任务."""
        with self.session() as s:
            from sqlalchemy.orm import joinedload
            return (
                s.query(CalendarTask)
                .options(joinedload(CalendarTask.fields), joinedload(CalendarTask.comments))
                .filter(CalendarTask.date == target_date)
                .order_by(CalendarTask.sort_order)
                .all()
            )

    def create_task(self, target_date: date, title: str = "新任务") -> CalendarTask:
        """创建任务."""
        with self.session() as s:
            max_order = (
                s.query(func.max(CalendarTask.sort_order))
                .filter(CalendarTask.date == target_date)
                .scalar() or 0
            )
            task = CalendarTask(date=target_date, title=title, sort_order=max_order + 1)
            s.add(task)
            s.flush()
            return task

    def get_task_by_id(self, task_id: int) -> Optional[CalendarTask]:
        with self.session() as s:
            from sqlalchemy.orm import joinedload
            return (
                s.query(CalendarTask)
                .options(joinedload(CalendarTask.fields), joinedload(CalendarTask.comments))
                .filter(CalendarTask.id == task_id)
                .first()
            )

    def update_task_title(self, task_id: int, title: str) -> bool:
        with self.session() as s:
            count = s.query(CalendarTask).filter(CalendarTask.id == task_id).update({"title": title})
            return count > 0

    def delete_task(self, task_id: int) -> bool:
        """删除任务（ORM 方式，触发 cascade 连带删除字段和评论）. """
        with self.session() as s:
            task = s.query(CalendarTask).filter(CalendarTask.id == task_id).first()
            if not task:
                return False
            s.delete(task)
            return True

    def add_task_field(self, task_id: int, content: str = "") -> CalendarTaskField:
        with self.session() as s:
            max_order = (
                s.query(func.max(CalendarTaskField.sort_order))
                .filter(CalendarTaskField.task_id == task_id)
                .scalar() or 0
            )
            field = CalendarTaskField(task_id=task_id, content=content, sort_order=max_order + 1)
            s.add(field)
            s.flush()
            return field

    def update_task_field(self, field_id: int, content: str) -> bool:
        with self.session() as s:
            count = s.query(CalendarTaskField).filter(CalendarTaskField.id == field_id).update({"content": content})
            return count > 0

    def delete_task_field(self, field_id: int) -> bool:
        with self.session() as s:
            count = s.query(CalendarTaskField).filter(CalendarTaskField.id == field_id).delete()
            return count > 0

    def add_comment(self, task_id: int, content: str, author: str = "我") -> CalendarComment:
        with self.session() as s:
            comment = CalendarComment(task_id=task_id, content=content, author=author)
            s.add(comment)
            s.flush()
            return comment

    def get_comments(self, task_id: int) -> List[CalendarComment]:
        with self.session() as s:
            return s.query(CalendarComment).filter(CalendarComment.task_id == task_id).order_by(CalendarComment.created_at).all()
