"""SQLAlchemy 数据模型定义."""

from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    """应用分类."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True, comment="分类名称")
    color = Column(String(7), nullable=False, default="#9E9E9E", comment="颜色 HEX")
    icon = Column(String(16), nullable=True, comment="图标字符")
    is_system = Column(Boolean, default=False, comment="系统预设分类")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now)

    sessions = relationship("AppSession", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"


class AppSession(Base):
    """单次应用使用时段 —— 记录同一窗口的连续使用."""

    __tablename__ = "app_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    process_name = Column(String(256), nullable=False, index=True, comment="进程名")
    executable_path = Column(String(1024), nullable=True, comment="可执行文件路径（用于提取图标）")
    window_title = Column(String(1024), nullable=True, comment="窗口标题")
    browser_page = Column(String(512), nullable=True, comment="浏览器页面标题（提取后）")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    duration_seconds = Column(Integer, nullable=False, default=0, comment="使用时长（秒）")
    is_idle = Column(Boolean, default=False, comment="是否空闲时段")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True, comment="分类ID")
    created_at = Column(DateTime, default=datetime.now)

    category = relationship("Category", back_populates="sessions")

    def __repr__(self) -> str:
        return (
            f"<AppSession(id={self.id}, process='{self.process_name}', "
            f"duration={self.duration_seconds}s, idle={self.is_idle})>"
        )


class AppCategory(Base):
    """应用 → 分类 映射表（手动 + 自动）. """

    __tablename__ = "app_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    process_name = Column(String(256), unique=True, nullable=False, index=True, comment="进程名")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, comment="分类ID")
    is_auto = Column(Boolean, default=False, comment="是否 LLM 自动分类")
    created_at = Column(DateTime, default=datetime.now)

    category = relationship("Category")

    def __repr__(self) -> str:
        return f"<AppCategory(process='{self.process_name}', cat_id={self.category_id})>"


class CalendarTask(Base):
    """日历任务 —— 某日的一个任务条."""
    __tablename__ = "calendar_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True, comment="所属日期")
    title = Column(String(256), nullable=False, default="新任务", comment="任务标题")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    fields = relationship("CalendarTaskField", back_populates="task", cascade="all, delete-orphan",
                          order_by="CalendarTaskField.sort_order")
    comments = relationship("CalendarComment", back_populates="task", cascade="all, delete-orphan",
                            order_by="CalendarComment.created_at")

    def __repr__(self) -> str:
        return f"<CalendarTask(id={self.id}, date='{self.date}', title='{self.title}')>"


class CalendarTaskField(Base):
    """任务文本字段 —— 类似 Notion 的内容块."""
    __tablename__ = "calendar_task_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("calendar_tasks.id"), nullable=False, comment="所属任务")
    content = Column(Text, default="", comment="文本内容")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now)

    task = relationship("CalendarTask", back_populates="fields")

    def __repr__(self) -> str:
        return f"<CalendarTaskField(id={self.id}, task_id={self.task_id})>"


class CalendarComment(Base):
    """任务评论."""
    __tablename__ = "calendar_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("calendar_tasks.id"), nullable=False, comment="所属任务")
    author = Column(String(64), default="我", comment="作者")
    content = Column(Text, nullable=False, comment="评论内容")
    created_at = Column(DateTime, default=datetime.now)

    task = relationship("CalendarTask", back_populates="comments")

    def __repr__(self) -> str:
        return f"<CalendarComment(id={self.id}, task_id={self.task_id})>"
