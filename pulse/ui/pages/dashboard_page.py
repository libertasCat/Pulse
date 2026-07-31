"""仪表盘页面 —— 三标签：应用统计 / 分类占比 / AI 分析."""

from datetime import date
from typing import Optional

from PyQt6.QtCore import QTimer, Qt  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from pulse.core.analyzer import AnalyzerService
from pulse.core.tracker import AppTracker
from pulse.db.repository import Repository
from pulse.ui.widgets.charts import HorizontalBarChart, PieChart
from pulse.utils.config import ConfigManager
from pulse.utils.icon_cache import get_app_icon
from pulse.utils.process_names import strip_ext

_BAR_COLORS = [
    "#7c5cfc", "#2196F3", "#4CAF50", "#FF9800",
    "#E91E63", "#00BCD4", "#9C27B0", "#FF5722",
    "#607D8B", "#795548", "#CDDC39", "#03A9F4",
]


class DashboardPage(QWidget):
    """仪表盘 —— 顶栏概览卡片 + 子标签页."""

    def __init__(self, tracker: Optional[AppTracker] = None, repo: Optional[Repository] = None,
                 config_mgr: Optional[ConfigManager] = None):
        super().__init__()
        self._tracker = tracker
        self._repo = repo
        self._config_mgr = config_mgr

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._build_header(layout)
        self._build_stat_cards(layout)
        self._build_tab_bar(layout)
        self._build_tab_pages(layout)

        # 定时刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def set_tracker(self, tracker: AppTracker) -> None:
        self._tracker = tracker

    # ── 构建顶栏 ──────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(16)
        title = QLabel("仪表盘")
        title.setObjectName("pageTitle")
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("pageSubtitle")
        row.addWidget(title)
        row.addWidget(self._subtitle, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(row)

    def _build_stat_cards(self, layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(16)
        self._card_values = {}
        for title in ("今日活跃时长", "使用应用数", "当前会话"):
            card, v_label = self._make_stat_card(title, "--")
            self._card_values[title] = v_label
            row.addWidget(card)
        layout.addLayout(row)

    @staticmethod
    def _make_stat_card(title: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(90)
        lo = QVBoxLayout(card)
        lo.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        v = QLabel(value)
        v.setObjectName("cardValue")
        lo.addWidget(t)
        lo.addWidget(v, alignment=Qt.AlignmentFlag.AlignLeft)
        return card, v

    # ── 标签栏 ────────────────────────────────────────────

    def _build_tab_bar(self, layout: QVBoxLayout):
        bar = QFrame()
        bar.setObjectName("card")
        bar.setFixedHeight(44)
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(2)

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.idClicked.connect(self._switch_tab)

        tabs = [(0, "应用统计"), (1, "分类占比"), (2, "AI 分析")]
        for tid, tname in tabs:
            btn = QPushButton(tname)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._tab_style())
            self._tab_group.addButton(btn, tid)
            lo.addWidget(btn)
        lo.addStretch()

        layout.addWidget(bar)
        if self._tab_group.buttons():
            self._tab_group.buttons()[0].setChecked(True)

    @staticmethod
    def _tab_style() -> str:
        return (
            "QPushButton { background: transparent; border: none; border-radius: 6px; "
            "padding: 4px 18px; font-size: 13px; color: #808098; }"
            "QPushButton:hover { background: #2a2a44; }"
            "QPushButton:checked { background: #7c5cfc; color: #ffffff; font-weight: 600; }"
        )

    # ── 标签页 ────────────────────────────────────────────

    def _build_tab_pages(self, layout: QVBoxLayout):
        self._tab_stack = QWidget()
        self._tab_stack.setObjectName("card")
        stack_lo = QVBoxLayout(self._tab_stack)
        stack_lo.setContentsMargins(16, 16, 16, 16)

        # ---------- Tab 0: 应用统计 ----------
        self._app_tab = QWidget()
        app_lo = QVBoxLayout(self._app_tab)
        app_lo.setContentsMargins(0, 0, 0, 0)
        app_title = QLabel("应用使用排行（今日）")
        app_title.setStyleSheet("font-size: 14px; font-weight: 600; margin-bottom: 8px;")
        app_lo.addWidget(app_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self._bar_chart = HorizontalBarChart()
        scroll.setWidget(self._bar_chart)
        app_lo.addWidget(scroll, stretch=1)
        stack_lo.addWidget(self._app_tab)

        # ---------- Tab 1: 分类占比 ----------
        self._cat_tab = QWidget()
        cat_lo = QVBoxLayout(self._cat_tab)
        cat_lo.setContentsMargins(0, 0, 0, 0)
        cat_title = QLabel("分类使用占比")
        cat_title.setStyleSheet("font-size: 14px; font-weight: 600; margin-bottom: 8px;")
        cat_lo.addWidget(cat_title)

        self._cat_placeholder = QLabel("应用分类尚未启用\n请先在设置中配置 LLM 自动分类或手动标记")
        self._cat_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cat_placeholder.setStyleSheet("color: #808098; font-size: 13px; padding: 40px;")

        self._pie_chart = PieChart()
        self._pie_chart.setVisible(False)

        cat_lo.addWidget(self._cat_placeholder)
        cat_lo.addWidget(self._pie_chart, stretch=1)
        stack_lo.addWidget(self._cat_tab)

        # ---------- Tab 2: AI 分析 ----------
        self._ai_tab = QWidget()
        ai_lo = QVBoxLayout(self._ai_tab)
        ai_lo.setContentsMargins(0, 0, 0, 0)

        # 周期选择 + 生成按钮
        ai_toolbar = QHBoxLayout()
        ai_toolbar.setSpacing(8)
        self._ai_period = QButtonGroup(self)
        self._ai_period.setExclusive(True)
        for pid, pname in ((0, "今日"), (1, "本周"), (2, "本月")):
            btn = QPushButton(pname)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._tab_style())
            self._ai_period.addButton(btn, pid)
            ai_toolbar.addWidget(btn)
        if self._ai_period.buttons():
            self._ai_period.buttons()[0].setChecked(True)

        self._ai_run_btn = QPushButton("🤖 生成分析")
        self._ai_run_btn.setFixedHeight(30)
        self._ai_run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_run_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 6px; "
            "padding: 4px 16px; color: #fff; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #6a4acc; }"
            "QPushButton:disabled { background: #4a4a6a; color: #808098; }"
        )
        self._ai_run_btn.clicked.connect(self._run_ai_analysis)
        ai_toolbar.addWidget(self._ai_run_btn)
        ai_toolbar.addStretch()
        ai_lo.addLayout(ai_toolbar)

        # 结果显示区
        self._ai_result = QTextEdit()
        self._ai_result.setReadOnly(True)
        self._ai_result.setPlaceholderText(
            "点击「生成分析」获取 AI 对你使用行为的洞察与建议"
        )
        self._ai_result.setStyleSheet(
            "QTextEdit { background: transparent; border: none; color: #c0c0d0; "
            "font-size: 13px; line-height: 1.6; }"
        )
        ai_lo.addWidget(self._ai_result, stretch=1)
        stack_lo.addWidget(self._ai_tab)

        self._cat_tab.setVisible(False)
        self._ai_tab.setVisible(False)

        layout.addWidget(self._tab_stack, stretch=1)

    def _switch_tab(self, tab_id: int):
        self._app_tab.setVisible(tab_id == 0)
        self._cat_tab.setVisible(tab_id == 1)
        self._ai_tab.setVisible(tab_id == 2)

    # ── AI 分析 ─────────────────────────────────────────

    def _run_ai_analysis(self):
        if not self._repo or not self._config_mgr:
            return
        llm_cfg = self._config_mgr.config.llm
        if not llm_cfg.api_key:
            self._ai_result.setPlainText("⚠️ 未配置 LLM API Key\n请前往 设置 → AI 分类 填写 DeepSeek API Key")
            return

        period_map = {0: "day", 1: "week", 2: "month"}
        pid = self._ai_period.checkedId()
        period = period_map.get(pid, "day")

        self._ai_run_btn.setEnabled(False)
        self._ai_run_btn.setText("分析中...")
        self._ai_result.setPlainText("正在调用 AI 分析，请稍候...")

        try:
            svc = AnalyzerService(self._repo, llm_cfg)
            result = svc.analyze(period)
            self._ai_result.setPlainText(result)
        except Exception as e:
            self._ai_result.setPlainText(f"分析失败: {e}")
        finally:
            self._ai_run_btn.setEnabled(True)
            self._ai_run_btn.setText("🤖 生成分析")

    # ── 刷新数据 ──────────────────────────────────────────

    def refresh(self):
        """页面切换时调用的公开刷新入口."""
        self._refresh()

    def _refresh(self):
        today = date.today()
        total_sec = 0
        top_apps: list = []

        if self._repo:
            try:
                total_sec = self._repo.get_total_duration_by_date(today)
                top_apps = self._repo.get_usage_summary_by_date(today, "process_name")
            except Exception:
                pass

        self._update_stat_cards(total_sec, top_apps)
        self._update_bar_chart(top_apps)
        self._update_pie_chart()

    def _update_stat_cards(self, total_sec: int, top_apps: list):
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        time_text = f"{h}h {m:02d}m" if h else f"{m}m"
        self._set_card("今日活跃时长", time_text)
        self._set_card("使用应用数", str(len(top_apps)))
        self._subtitle.setText(f"{date.today().isoformat()}  ·  共 {len(top_apps)} 个应用")

        if self._tracker and self._tracker.current_session:
            cur = self._tracker.current_session
            self._set_card("当前会话", f"{strip_ext(cur.process_name)}  {cur.duration_seconds}s")
        else:
            self._set_card("当前会话", "---")

    def _update_bar_chart(self, top_apps: list):
        data = []
        for i, app in enumerate(top_apps[:10]):
            raw_name = app["name"]            # 完整进程名（用于查找）
            disp_name = strip_ext(raw_name)   # 去后缀（用于显示）
            secs = app["total_seconds"]
            color = _BAR_COLORS[i % len(_BAR_COLORS)]
            # 获取 exe 路径并提取图标
            exe_path = None
            if self._repo:
                try:
                    exe_path = self._repo.get_latest_exe_path(raw_name)
                except Exception:
                    pass
            # 同时扫描正在运行的进程（兜底）
            if not exe_path:
                try:
                    import psutil
                    for proc in psutil.process_iter(['name', 'exe']):
                        if proc.info.get('name') == raw_name and proc.info.get('exe'):
                            exe_path = proc.info['exe']
                            break
                except Exception:
                    pass
            icon = get_app_icon(raw_name, exe_path)
            data.append((disp_name, secs, color, icon))
        self._bar_chart.set_data(data)

    def _update_pie_chart(self):
        if not self._repo:
            return
        try:
            today = date.today()
            cats = self._repo.get_all_categories()

            # 获取已分类的应用
            app_cats = self._repo.get_all_app_categories()
            app_to_cat = {a["process_name"]: a for a in app_cats}

            apps_today = self._repo.get_usage_summary_by_date(today, "process_name")
            cat_seconds: dict[int, int] = {}

            for app in apps_today:
                pname = app["name"]
                secs = app["total_seconds"]
                mapping = app_to_cat.get(pname)
                if mapping:
                    cid = mapping["category_id"]
                    cat_seconds[cid] = cat_seconds.get(cid, 0) + secs

            cat_data = []
            has_values = False
            for cat in cats:
                secs = cat_seconds.get(cat.id, 0)
                if secs > 0:
                    has_values = True
                cat_data.append((cat.name, secs, cat.color or "#9E9E9E"))

            if not has_values:
                self._cat_placeholder.setText(
                    "尚无分类数据\n请前往设置 → 应用分类 为应用分配分类"
                    if not app_to_cat else
                    "今日暂无已分类的应用使用记录"
                )
                self._cat_placeholder.setVisible(True)
                self._pie_chart.setVisible(False)
            else:
                self._cat_placeholder.setVisible(False)
                self._pie_chart.setVisible(True)
                self._pie_chart.set_data(cat_data)
        except Exception as e:
            # 保留调试信息以便排查
            import logging
            logging.getLogger(__name__).warning("饼图更新失败: %s", e)

    def _set_card(self, title: str, value: str):
        label = self._card_values.get(title)
        if label:
            label.setText(value)
