"""AI 知识库问答测试。"""
from shengxuezhidao.ai import Assistant
from shengxuezhidao.ai.kb import KnowledgeBase
from shengxuezhidao.core.catalog import Catalog
from shengxuezhidao.data.seed import load_seed


def _kb():
    c = Catalog()
    load_seed(c)
    return KnowledgeBase(c)


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
    kb = _kb()
    asst = Assistant(kb)
    ans = asst.ask("曼彻斯特大学高考要多少分")
    assert "Manchester" in ans.text or "曼彻斯特" in ans.text
    assert ans.source == "local-retrieval"


def test_clarify_asks_missing_fields():
    kb = _kb()
    asst = Assistant(kb)
    from shengxuezhidao.core.models import StudentProfile
    p = StudentProfile(nationality="CN", education_route="")
    qs = asst.clarify(p)
    assert any("课程" in q for q in qs)
