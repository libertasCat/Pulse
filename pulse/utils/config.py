"""配置管理模块."""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from pulse.utils.constants import DATA_DIR, DEFAULT_POLL_INTERVAL, DEFAULT_IDLE_THRESHOLD

logger = logging.getLogger(__name__)

CONFIG_FILE = DATA_DIR / "config.json"


@dataclass
class LLMConfig:
    """LLM 配置.

    provider 可选值:
      - "deepseek"  : DeepSeek API（默认）
      - "kimi"      : Kimi / Moonshot API
      - "openai"    : OpenAI API
      - "ollama"    : 本地 Ollama
      - "openai-compatible": 其他兼容 OpenAI 格式的 API
    """
    provider: str = "deepseek"
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: Optional[str] = None  # 默认 None，按 provider 自动选择
    enabled: bool = False

    # 各厂商预设模型（可自由输入其他模型名）
    PRESET_MODELS = {
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "kimi": ["kimi-k2-0711-preview", "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini"],
        "ollama": ["llama3", "qwen2.5", "deepseek-r1"],
        "openai-compatible": [],
    }

    def __post_init__(self):
        # 未指定 base_url 时按 provider 自动填充
        if self.base_url is None:
            defaults = {
                "deepseek": "https://api.deepseek.com",
                "kimi": "https://api.moonshot.cn/v1",
                "openai": "https://api.openai.com/v1",
                "ollama": "http://localhost:11434/v1",
            }
            self.base_url = defaults.get(self.provider, "")

    def to_dict(self):
        d = asdict(self)
        if d["api_key"]:
            d["api_key"] = "***"
        return d


@dataclass
class TrackerConfig:
    """追踪器配置."""
    poll_interval: float = DEFAULT_POLL_INTERVAL
    idle_threshold: int = DEFAULT_IDLE_THRESHOLD


@dataclass
class AppConfig:
    """应用全局配置."""
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    excluded_processes: list = field(default_factory=list)
    auto_start: bool = False
    minimize_to_tray: bool = True
    theme: str = "light"  # light / dark
    language: str = "zh"


class ConfigManager:
    """配置管理器 —— 负责 JSON 配置文件的读写."""

    def __init__(self, config_path: Path = CONFIG_FILE):
        self._path = config_path
        self._config: Optional[AppConfig] = None

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self.load()
        return self._config

    def load(self) -> AppConfig:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = self._from_dict(data)
                logger.info(f"配置已加载: {self._path}")
            except Exception as e:
                logger.warning(f"配置加载失败，使用默认值: {e}")
                self._config = AppConfig()
        else:
            logger.info(f"配置文件不存在，使用默认值: {self._path}")
            self._config = AppConfig()
        return self._config

    def save(self) -> None:
        if self._config is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(self._config), f, ensure_ascii=False, indent=2)
        logger.info(f"配置已保存: {self._path}")

    @staticmethod
    def _from_dict(data: dict) -> AppConfig:
        return AppConfig(
            tracker=TrackerConfig(**data.get("tracker", {})),
            llm=LLMConfig(**{k: v for k, v in data.get("llm", {}).items() if k in LLMConfig.__dataclass_fields__}),
            excluded_processes=data.get("excluded_processes", []),
            auto_start=data.get("auto_start", False),
            minimize_to_tray=data.get("minimize_to_tray", True),
            theme=data.get("theme", "light"),
            language=data.get("language", "zh"),
        )

    @staticmethod
    def _to_dict(config: AppConfig) -> dict:
        return {
            "tracker": asdict(config.tracker),
            "llm": asdict(config.llm),
            "excluded_processes": config.excluded_processes,
            "auto_start": config.auto_start,
            "minimize_to_tray": config.minimize_to_tray,
            "theme": config.theme,
            "language": config.language,
        }
