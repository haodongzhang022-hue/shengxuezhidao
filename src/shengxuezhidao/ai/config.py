"""LLM 接入配置模块。

设计目标:
- 默认接入 DeepSeek(OpenAI 兼容接口), 开箱即用
- 支持通过 环境变量 / JSON 配置文件 / 构造参数 覆盖为任意 OpenAI 兼容大模型
- 统一的配置加载优先级: 构造参数 > 环境变量 > 配置文件 > 内置默认值

支持的配置项(前缀 SXZD_LLM_):
  SXZD_LLM_API_KEY    - API 密钥(必填才能真正发起生成式请求)
  SXZD_LLM_BASE_URL   - API 基础地址(默认 DeepSeek: https://api.deepseek.com)
  SXZD_LLM_MODEL      - 模型名(默认 deepseek-chat)
  SXZD_LLM_PROVIDER   - 提供商名(默认 deepseek; 可选 openai/qwen/glm/ollama 等)
  SXZD_LLM_TIMEOUT    - 请求超时(秒, 默认 60)
  SXZD_LLM_MAX_TOKENS - 生成上限(默认 2048)
  SXZD_LLM_TEMPERATURE- 采样温度(默认 0.2)
  SXZD_LLM_ENABLED    - 是否启用 LLM(默认 auto: 有 API_KEY 即启用)
  SXZD_LLM_CONFIG     - 指向 JSON 配置文件的路径(可选, 优先级低于上述单值环境变量)
  SXZD_LLM_HTTP_REFERER / SXZD_LLM_HTTP_UA - 自定义 HTTP 头(可选, 用于特殊网关)

配置文件示例 (sxzd_llm.json):
{
  "api_key": "sk-xxxx",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "provider": "deepseek",
  "timeout": 60,
  "max_tokens": 2048,
  "temperature": 0.2,
  "enabled": true,
  "headers": {"X-Custom": "value"}
}
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


# DeepSeek 官方默认配置
DEFAULT_PROVIDER = "deepseek"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.2

# 常见 OpenAI 兼容提供商预设(便于用户一键切换)
KNOWN_PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
    },
}


@dataclass
class LLMConfig:
    """大模型接入配置(默认指向 DeepSeek)。"""
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    provider: str = DEFAULT_PROVIDER
    timeout: int = DEFAULT_TIMEOUT
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    enabled: Optional[bool] = None      # None=auto(有 key 即启用)
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def effective_enabled(self) -> bool:
        """实际是否启用 LLM: 显式配置优先, 否则取决于有无 api_key。"""
        if self.enabled is not None:
            return self.enabled
        return bool(self.api_key)

    @classmethod
    def from_file(cls, path: str | os.PathLike) -> Optional["LLMConfig"]:
        p = Path(path)
        if not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, d: dict) -> "LLMConfig":
        return cls(
            api_key=str(d.get("api_key", "")),
            base_url=str(d.get("base_url", "")),   # 未显式设置则为空串
            model=str(d.get("model", "")),          # 未显式设置则为空串
            provider=str(d.get("provider", "")),    # 未显式设置则为空串
            timeout=int(d.get("timeout", DEFAULT_TIMEOUT)),
            max_tokens=int(d.get("max_tokens", DEFAULT_MAX_TOKENS)),
            temperature=float(d.get("temperature", DEFAULT_TEMPERATURE)),
            enabled=d.get("enabled"),
            headers=dict(d.get("headers", {}) or {}),
        )

    @classmethod
    def load(cls, api_key: Optional[str] = None,
             base_url: Optional[str] = None,
             model: Optional[str] = None,
             provider: Optional[str] = None) -> "LLMConfig":
        """按优先级加载配置: 构造参数 > 环境变量 > 配置文件 > 默认值。

        优先级:
            CLI 参数  >  环境变量  >  JSON 配置文件  >  provider 预设  >  内置默认
        """
        # 1. 读取环境变量
        env_provider = os.getenv("SXZD_LLM_PROVIDER", "")
        env_key = os.getenv("SXZD_LLM_API_KEY", "")
        env_url = os.getenv("SXZD_LLM_BASE_URL", "")
        env_model = os.getenv("SXZD_LLM_MODEL", "")
        env_timeout = os.getenv("SXZD_LLM_TIMEOUT", "")
        env_max_tokens = os.getenv("SXZD_LLM_MAX_TOKENS", "")
        env_temp = os.getenv("SXZD_LLM_TEMPERATURE", "")
        env_enabled = os.getenv("SXZD_LLM_ENABLED", "")

        # 2. 读取配置文件(可选)
        cfg_file = os.getenv("SXZD_LLM_CONFIG", "")
        file_cfg = cls.from_file(cfg_file) if cfg_file else None

        # 3. 确定最终 provider
        prov = (
            provider or env_provider
            or (file_cfg.provider if file_cfg else None)
            or DEFAULT_PROVIDER
        )
        preset = KNOWN_PROVIDERS.get(prov, {})

        # 4. 从默认值开始构建
        merged = cls()
        merged.provider = prov

        # 5. 逐字段按优先级合并
        # base_url: CLI > env > file > preset > default
        merged.base_url = (
            base_url or env_url
            or (file_cfg.base_url if file_cfg else None)
            or preset.get("base_url", DEFAULT_BASE_URL)
        )
        # model: CLI > env > file > preset > default
        merged.model = (
            model or env_model
            or (file_cfg.model if file_cfg else None)
            or preset.get("model", DEFAULT_MODEL)
        )
        # api_key: CLI > env > file
        merged.api_key = (
            api_key or env_key
            or (file_cfg.api_key if file_cfg else "")
        )
        # timeout / max_tokens / temperature / enabled
        if env_timeout:
            merged.timeout = int(env_timeout)
        elif file_cfg is not None:
            merged.timeout = file_cfg.timeout
        if env_max_tokens:
            merged.max_tokens = int(env_max_tokens)
        elif file_cfg is not None:
            merged.max_tokens = file_cfg.max_tokens
        if env_temp:
            merged.temperature = float(env_temp)
        elif file_cfg is not None:
            merged.temperature = file_cfg.temperature
        if env_enabled:
            merged.enabled = env_enabled.lower() in ("1", "true", "yes", "on")
        elif file_cfg is not None:
            merged.enabled = file_cfg.enabled

        # 6. headers 合并
        if file_cfg is not None:
            merged.headers = dict(file_cfg.headers)

        # 7. 附加自定义 HTTP 头(来自环境变量)
        extra_headers = {}
        for k in ("SXZD_LLM_HTTP_REFERER", "SXZD_LLM_HTTP_UA"):
            v = os.getenv(k)
            if v:
                hname = "Referer" if "REFERER" in k else "User-Agent"
                extra_headers[hname] = v
        if extra_headers:
            merged.headers.update(extra_headers)

        return merged

    def to_env_payload(self) -> str:
        """生成可直接粘贴到 shell 的配置示例(便于用户快速接入)。"""
        return (f"export SXZD_LLM_API_KEY={self.api_key}\n"
                f"export SXZD_LLM_BASE_URL={self.base_url}\n"
                f"export SXZD_LLM_MODEL={self.model}\n"
                f"export SXZD_LLM_PROVIDER={self.provider}")
