"""LLM API 客户端 —— 兼容 DeepSeek / OpenAI / Ollama."""

import logging
from typing import Optional

from pulse.utils.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM API 客户端，自动根据 config.provider 选择端点."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self._config = config
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self._config and self._config.api_key)

    def _get_client(self):
        """懒加载 OpenAI 客户端."""
        if self._client is None and self._config:
            try:
                from openai import OpenAI
            except ModuleNotFoundError:
                import subprocess, sys
                logger.warning("openai 包未安装，尝试自动安装...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "openai", "-q"]
                )
                from openai import OpenAI
            self._client = OpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url or "https://api.deepseek.com",
            )
        return self._client

    def classify_apps(self, apps: list[str], categories: list[str]) -> dict[str, str]:
        """批量分类应用 —— 应用名 → 分类名 的映射.

        Args:
            apps: 待分类的应用列表（如 ["chrome.exe", "code.exe"]）
            categories: 可用分类列表（如 ["开发工具", "浏览器", ...]）

        Returns:
            {process_name: category_name} 映射
        """
        if not apps or not self.is_configured:
            return {}

        client = self._get_client()
        if not client:
            return {}

        # 分批处理，每批最多 20 个
        batch_size = 20
        result = {}
        for i in range(0, len(apps), batch_size):
            batch = apps[i:i + batch_size]
            try:
                batch_result = self._classify_batch(batch, categories)
                result.update(batch_result)
            except Exception as e:
                logger.error("分类批处理失败: %s", e)
        return result

    def _classify_batch(self, apps: list[str], categories: list[str]) -> dict[str, str]:
        """调用 LLM 对一批应用进行分类."""
        model = self._config.model or "deepseek-chat"
        cat_list = "\n".join(f"- {c}" for c in categories)
        app_list = "\n".join(apps)

        prompt = (
            f"你是一个应用分类助手。请根据进程名将以下应用归类到已有分类中。\n\n"
            f"可用分类：\n{cat_list}\n\n"
            f"应用列表：\n{app_list}\n\n"
            f"请返回 JSON 格式（不要代码块，纯 JSON）：{{ \"应用进程名\": \"分类名\" }}\n"
            f"只返回 JSON，不要额外说明。"
        )

        client = self._get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        import json
        try:
            mapping = json.loads(content)
            # 验证键值
            valid = {}
            for app in apps:
                cat_name = mapping.get(app)
                if cat_name and cat_name in categories:
                    valid[app] = cat_name
                elif cat_name:
                    # 尝试模糊匹配
                    for c in categories:
                        if cat_name.lower() in c.lower() or c.lower() in cat_name.lower():
                            valid[app] = c
                            break
            return valid
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("LLM 返回解析失败: %s", e)
            return {}

    def generate_daily_summary(self, usage_data: str) -> str:
        """生成每日总结."""
        client = self._get_client()
        if not client:
            return ""
        try:
            resp = client.chat.completions.create(
                model=self._config.model or "deepseek-chat",
                messages=[{
                    "role": "user",
                    "content": f"请用一句话总结今天的使用情况：\n{usage_data}"
                }],
                temperature=0.5,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error("生成每日总结失败: %s", e)
            return ""
