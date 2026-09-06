"""AI 知识库问答测试。"""
import os
import json
import tempfile

from shengxuezhidao.ai import Assistant, LLMConfig, KNOWN_PROVIDERS
from shengxuezhidao.ai.kb import KnowledgeBase
from shengxuezhidao.core.catalog import Catalog
from shengxuezhidao.data.seed import load_seed


def _kb():
    c = Catalog()
    load_seed(c)
    return KnowledgeBase(c)


def _clean_env():
    """清除可能干扰测试的 LLM 环境变量。"""
    for k in list(os.environ):
        if k.startswith("SXZD_LLM_"):
            del os.environ[k]


def test_retrieve_chinese_school():
    kb = _kb()
    chunks = kb.retrieve("曼彻斯特大学高考要求", top_k=5)
    assert chunks
    assert any(c.school == "University of Manchester" for c in chunks)


def test_retrieve_country_alias():
    kb = _kb()
    chunks = kb.retrieve("澳洲哪些学校接受高考", top_k=5)
    assert chunks
    assert any(c.country == "澳大利亚" for c in chunks)


def test_ask_local_answer():
    _clean_env()
    kb = _kb()
    asst = Assistant(kb)
    ans = asst.ask("曼彻斯特大学高考要多少分")
    assert "Manchester" in ans.text or "曼彻斯特" in ans.text
    assert ans.source == "local-retrieval"


def test_clarify_asks_missing_fields():
    _clean_env()
    kb = _kb()
    asst = Assistant(kb)
    from shengxuezhidao.core.models import StudentProfile
    p = StudentProfile(nationality="CN", education_route="")
    qs = asst.clarify(p)
    assert any("课程" in q for q in qs)


# ---------------- LLM 配置测试 ----------------

def test_default_config_points_to_deepseek():
    """默认配置应指向 DeepSeek。"""
    _clean_env()
    cfg = LLMConfig.load()
    assert cfg.base_url == "https://api.deepseek.com"
    assert cfg.model == "deepseek-chat"
    assert cfg.provider == "deepseek"
    assert cfg.effective_enabled is False  # 无 key 时不启用


def test_config_from_env():
    """环境变量应能覆盖配置。"""
    _clean_env()
    os.environ["SXZD_LLM_API_KEY"] = "sk-test-123"
    os.environ["SXZD_LLM_MODEL"] = "custom-model"
    os.environ["SXZD_LLM_BASE_URL"] = "https://example.com/v1"
    cfg = LLMConfig.load()
    assert cfg.api_key == "sk-test-123"
    assert cfg.model == "custom-model"
    assert cfg.base_url == "https://example.com/v1"
    assert cfg.effective_enabled is True
    _clean_env()


def test_config_from_json_file():
    """JSON 配置文件应可加载。"""
    _clean_env()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False, encoding="utf-8") as f:
        json.dump({
            "provider": "openai",
            "api_key": "sk-file-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
        }, f)
        path = f.name
    os.environ["SXZD_LLM_CONFIG"] = path
    cfg = LLMConfig.load()
    assert cfg.provider == "openai"
    assert cfg.api_key == "sk-file-key"
    assert cfg.model == "gpt-4o-mini"
    os.unlink(path)
    _clean_env()


def test_provider_presets():
    """内置 provider 预设应正确映射。"""
    assert "deepseek" in KNOWN_PROVIDERS
    assert "openai" in KNOWN_PROVIDERS
    assert "qwen" in KNOWN_PROVIDERS
    assert "glm" in KNOWN_PROVIDERS
    assert "ollama" in KNOWN_PROVIDERS


def test_config_priority_cli_over_env():
    """构造参数优先级应高于环境变量。"""
    _clean_env()
    os.environ["SXZD_LLM_API_KEY"] = "sk-env-key"
    os.environ["SXZD_LLM_MODEL"] = "env-model"
    os.environ["SXZD_LLM_BASE_URL"] = "https://env.example.com"
    cfg = LLMConfig.load(
        api_key="sk-cli-key",
        model="cli-model",
        base_url="https://cli.example.com",
    )
    assert cfg.api_key == "sk-cli-key"
    assert cfg.model == "cli-model"
    assert cfg.base_url == "https://cli.example.com"
    _clean_env()


def test_llm_ready_state():
    """有 key 时应 ready, 无 key 时不应 ready。"""
    _clean_env()
    kb = _kb()
    # 无 key: 不 ready
    asst = Assistant(kb)
    assert asst.llm_ready is False
    # 有 key: ready
    asst2 = Assistant(kb, api_key="sk-test")
    assert asst2.llm_ready is True
    assert asst2.config.model == "deepseek-chat"
    assert asst2.config.provider == "deepseek"


def test_source_label():
    """source_label 应正确反映引擎类型。"""
    _clean_env()
    kb = _kb()
    asst = Assistant(kb)
    assert "local-retrieval" in asst.source_label
    asst2 = Assistant(kb, api_key="sk-test")
    assert "llm" in asst2.source_label
    assert "deepseek" in asst2.source_label


def test_file_provider_preset_applies():
    """JSON 文件设置 provider 但未设 base_url/model 时, 应自动用该 provider 预设值。"""
    _clean_env()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False, encoding="utf-8") as f:
        json.dump({
            "provider": "qwen",
            "api_key": "sk-qwen-test",
            # 故意不设置 base_url / model
        }, f)
        path = f.name
    os.environ["SXZD_LLM_CONFIG"] = path
    cfg = LLMConfig.load()
    assert cfg.provider == "qwen"
    assert cfg.api_key == "sk-qwen-test"
    # 应从 qwen preset 自动填充 base_url 和默认 model
    assert cfg.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert cfg.model == "qwen-plus"
    os.unlink(path)
    _clean_env()


def test_file_custom_overrides_preset():
    """JSON 文件显式覆盖时, 应优先于 preset。"""
    _clean_env()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False, encoding="utf-8") as f:
        json.dump({
            "provider": "qwen",
            "api_key": "sk-qwen-test",
            "model": "qwen-max",
            "base_url": "https://custom-proxy.example.com/v1",
        }, f)
        path = f.name
    os.environ["SXZD_LLM_CONFIG"] = path
    cfg = LLMConfig.load()
    assert cfg.provider == "qwen"
    assert cfg.model == "qwen-max"
    assert cfg.base_url == "https://custom-proxy.example.com/v1"
    os.unlink(path)
    _clean_env()
