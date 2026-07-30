"""AI 分类服务 —— 调用 LLM 自动分类应用."""

import logging
from typing import Optional

from pulse.db.repository import Repository
from pulse.services.llm_client import LLMClient
from pulse.utils.config import LLMConfig

logger = logging.getLogger(__name__)


class ClassifierService:
    """分类服务 —— 获取未分类应用 → 调用 LLM → 保存映射."""

    def __init__(self, repo: Repository, llm_config: Optional[LLMConfig] = None):
        self._repo = repo
        self._llm = LLMClient(llm_config) if llm_config else None

    def reclassify(self) -> dict:
        """重新分类所有未分类的应用.

        Returns:
            {"success": [分类成功的应用数], "total": [待分类总数], "errors": [...]}
        """
        if not self._llm or not self._llm.is_configured:
            return {"success": 0, "total": 0, "errors": ["LLM 未配置"]}

        try:
            unclassified = self._repo.get_unclassified_processes()
            if not unclassified:
                return {"success": 0, "total": 0, "errors": []}

            cats = self._repo.get_all_categories()
            cat_names = [c.name for c in cats]

            mapping = self._llm.classify_apps(unclassified, cat_names)

            success = 0
            for process_name, cat_name in mapping.items():
                cat = self._repo.get_category_by_name(cat_name)
                if cat:
                    self._repo.save_app_category(process_name, cat.id, is_auto=True)
                    success += 1

            logger.info("分类完成: %d/%d 个应用已自动分类", success, len(unclassified))
            return {"success": success, "total": len(unclassified), "errors": []}

        except Exception as e:
            logger.error("自动分类失败: %s", e)
            return {"success": 0, "total": 0, "errors": [str(e)]}
