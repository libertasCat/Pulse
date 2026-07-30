"""AI 分类服务 —— 自动对热门未分类应用进行分类."""

import logging
from typing import Optional

from pulse.db.repository import Repository
from pulse.services.llm_client import LLMClient
from pulse.utils.config import LLMConfig

logger = logging.getLogger(__name__)

_HOT_THRESHOLD = 60   # 使用超过 60 秒的应用才自动分类
_MAX_PER_RUN = 10     # 每次最多分类 10 个


class ClassifierService:
    """分类服务 —— 自动识别热门未分类应用并调用 LLM 分类."""

    def __init__(self, repo: Repository, llm_config: Optional[LLMConfig] = None):
        self._repo = repo
        self._llm = LLMClient(llm_config) if llm_config else None

    def auto_classify(self) -> dict:
        """自动分类：获取所有未分类进程 → 按总使用时长排序 → 取前 N 个 → 调 LLM.

        Returns:
            {"success": N, "total": M, "hot": K, "errors": [...]}
        """
        if not self._llm or not self._llm.is_configured:
            logger.info("LLM 未配置，跳过自动分类")
            return {"success": 0, "total": 0, "hot": 0, "errors": ["LLM 未配置"]}

        try:
            # 1. 获取未分类进程及其总使用时长
            unclassified = self._repo.get_unclassified_processes()
            if not unclassified:
                return {"success": 0, "total": 0, "hot": 0, "errors": []}

            # 2. 按使用时长降序排列
            from datetime import date, timedelta
            hot_30d = date.today() - timedelta(days=30)
            scored = []
            for proc in unclassified:
                # 尝试获取最近30天的总时长
                try:
                    total = 0
                    for i in range(30):
                        d = hot_30d + timedelta(days=i)
                        total += self._repo.get_total_duration_by_date(d)
                except Exception:
                    total = 0
                scored.append((proc, total))
            scored.sort(key=lambda x: -x[1])

            # 3. 筛选热门应用（使用超过阈值）
            hot_apps = [p for p, s in scored if s >= _HOT_THRESHOLD][:_MAX_PER_RUN]
            if not hot_apps:
                return {"success": 0, "total": len(unclassified), "hot": 0, "errors": []}

            # 4. 调用 LLM 分类
            cats = self._repo.get_all_categories()
            cat_names = [c.name for c in cats]

            mapping = self._llm.classify_apps(hot_apps, cat_names)

            success = 0
            for process_name, cat_name in mapping.items():
                cat = self._repo.get_category_by_name(cat_name)
                if cat:
                    self._repo.save_app_category(process_name, cat.id, is_auto=True)
                    success += 1

            logger.info("自动分类: %d/%d 个热门应用已分类", success, len(hot_apps))
            return {"success": success, "total": len(unclassified), "hot": len(hot_apps), "errors": []}

        except Exception as e:
            logger.error("自动分类失败: %s", e)
            return {"success": 0, "total": 0, "hot": 0, "errors": [str(e)]}

    def classify_all(self) -> dict:
        """一次性分类所有未分类应用（保留作为手动触发）. """
        return self.auto_classify()
