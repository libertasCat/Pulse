"""SQLAlchemy 数据模型定义."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
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
