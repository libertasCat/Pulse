"""行为分析服务 —— 汇总使用数据并调用 LLM 生成分析建议."""

import logging
from datetime import date, timedelta
from typing import Optional

from pulse.db.repository import Repository
from pulse.services.llm_client import LLMClient
from pulse.utils.config import LLMConfig

logger = logging.getLogger(__name__)


class AnalyzerService:
    """分析服务：按日/周/月汇总使用数据 → LLM 生成分析."""

    def __init__(self, repo: Repository, llm_config: Optional[LLMConfig] = None):
        self._repo = repo
        self._llm = LLMClient(llm_config) if llm_config else None

    def analyze(self, period: str = "day") -> str:
        """生成指定周期的分析报告.

        Args:
            period: "day" / "week" / "month"

        Returns:
            分析文本（Markdown 风格）
        """
        if not self._llm or not self._llm.is_configured:
            return "⚠️ 未配置 LLM API Key，请前往 设置 → AI 分类 填写。"

        today = date.today()
        try:
            stats_text = self._build_stats(period, today)
            if not stats_text.strip():
                return "该周期暂无使用数据，无法分析。"
            label = {"day": "今日", "week": "本周", "month": "本月"}.get(period, "今日")
            return self._llm.analyze_usage(label, stats_text)
        except Exception as e:
            logger.error("分析失败: %s", e)
            return f"分析失败: {e}"

    def _build_stats(self, period: str, today: date) -> str:
        """构建统计数据文本."""
        if period == "day":
            days = [today]
            label = f"{today.isoformat()}"
        elif period == "week":
            monday = today - timedelta(days=today.weekday())
            days = [monday + timedelta(days=i) for i in range(7)]
            label = f"{monday.isoformat()} ~ {(monday + timedelta(days=6)).isoformat()}"
        else:
            days = [today - timedelta(days=i) for i in range(29, -1, -1)]
            label = f"{days[0].isoformat()} ~ {today.isoformat()}"

        lines = [f"统计周期: {label}"]
        total_sec = 0

        # 各应用总时长
        app_totals: dict[str, int] = {}
        for d in days:
            total_sec += self._repo.get_total_duration_by_date(d)
            for app in self._repo.get_usage_summary_by_date(d, "process_name"):
                app_totals[app["name"]] = app_totals.get(app["name"], 0) + app["total_seconds"]

        if not app_totals:
            return ""

        lines.append(f"总活跃时长: {total_sec // 3600} 小时 {total_sec % 3600 // 60} 分钟")
        lines.append(f"使用应用数: {len(app_totals)}")

        lines.append("\n应用使用时长 TOP 10:")
        for name, secs in sorted(app_totals.items(), key=lambda x: -x[1])[:10]:
            h, m = secs // 3600, (secs % 3600) // 60
            lines.append(f"- {name}: {h}小时{m}分钟")

        # 分类分布
        lines.append("\n分类分布:")
        cats = self._repo.get_all_categories()
        app_cats = self._repo.get_all_app_categories()
        app_to_cat = {a["process_name"]: a["category_id"] for a in app_cats}
        cat_secs: dict[str, int] = {}
        for name, secs in app_totals.items():
            cid = app_to_cat.get(name)
            if cid:
                cat = self._repo.get_category_by_id(cid)
                if cat:
                    cat_secs[cat.name] = cat_secs.get(cat.name, 0) + secs
        for cname, secs in sorted(cat_secs.items(), key=lambda x: -x[1]):
            h, m = secs // 3600, (secs % 3600) // 60
            lines.append(f"- {cname}: {h}小时{m}分钟")

        return "\n".join(lines)
