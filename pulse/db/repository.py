"""数据访问层 —— 封装所有数据库操作."""

import logging
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session as SASession, sessionmaker

from pulse.db.models import Base, AppSession, Category
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
        self._seed_default_categories()
        logger.info("数据库初始化完成")

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
