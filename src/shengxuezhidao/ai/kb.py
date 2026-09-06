"""知识库: 把 Catalog 的学校/路径数据转成可检索的文本片段。

用于"带知识库效果的增强检索与二次询问": 先检索相关片段作为上下文,
再(可选)喂给大模型生成自然语言回答; 无大模型时退化为检索问答。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.catalog import Catalog
from ..core.models import School
from ..engine.rules import ROUTE_LABEL

# 学校中英文别名 / 常见简写(提高中文提问命中)
SCHOOL_ALIAS = {
    "imperial college london": ["帝国理工", "帝国理工学院", "IC", "imperial"],
    "university of cambridge": ["剑桥", "剑桥大学", "cambridge"],
    "university of oxford": ["牛津", "牛津大学", "oxford"],
    "university of manchester": ["曼彻斯特大学", "曼大", "曼彻斯特", "manchester"],
    "university of edinburgh": ["爱丁堡大学", "爱丁堡", "edinburgh"],
    "university of melbourne": ["墨尔本大学", "墨尔本", "melbourne"],
    "university of sydney": ["悉尼大学", "悉尼", "sydney"],
    "university of toronto": ["多伦多大学", "多伦多", "toronto"],
    "university of british columbia": ["英属哥伦比亚大学", "UBC", "ubc"],
    "university of hong kong": ["香港大学", "港大", "hku"],
    "the chinese university of hong kong": ["香港中文大学", "港中文", "cuhk"],
    "national university of singapore": ["新加坡国立大学", "新国立", "NUS", "nus"],
    "nanyang technological university": ["南洋理工大学", "南大", "NTU", "ntu"],
    "stanford university": ["斯坦福", "斯坦福大学", "stanford"],
    "university of california, berkeley": ["加州大学伯克利", "伯克利", "UCB", "berkeley"],
    "university of michigan": ["密歇根大学", "密歇根", "michigan"],
    "arizona state university": ["亚利桑那州立大学", "亚利桑那州立", "ASU"],
}
# 国家/地区同义词
COUNTRY_ALIAS = {
    "英国": ["英国", "uk", "england", "英"],
    "美国": ["美国", "usa", "us", "美", "美本", "美利坚"],
    "澳大利亚": ["澳洲", "澳大利亚", "australia", "澳"],
    "加拿大": ["加拿大", "canada", "加"],
    "中国香港": ["香港", "hk", "港"],
    "新加坡": ["新加坡", "singapore", "坡"],
    "中国": ["中国", "china", "内地"],
}
# 需求关键词同义词
REQ_ALIAS = {
    "高考": ["高考", "gaokao", "国内高考"],
    "alevel": ["alevel", "a-level", "a level", "al", "a水准"],
    "ap": ["ap课程", "ap 课程"],
    "ib": ["ib", "国际文凭"],
    "雅思": ["雅思", "ielts"],
    "托福": ["托福", "toefl"],
    "语言": ["语言", "英语", "雅思", "托福", "语言要求"],
}


@dataclass
class Chunk:
    school: str
    country: str
    qs_rank: int
    text: str
    score: float = 0.0


class KnowledgeBase:
    """基于学校 Catalog 的轻量本地知识库(文本片段 + 关键词打分检索)。"""

    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self._chunks: List[Chunk] = []
        self.rebuild()

    def rebuild(self) -> None:
        self._chunks = []
        for s in self.catalog.all():
            for p in s.paths:
                r = p.requirement
                bits = [
                    f"{s.name}（{s.country}，QS {s.qs_rank}）在「"
                    f"{ROUTE_LABEL.get(p.path_type, p.path_type)}」线路下的要求：",
                ]
                if r.language_required and r.language_score:
                    bits.append(f"语言要求 {r.language_required} 不低于 {r.language_score}")
                    if r.language_note:
                        bits.append(r.language_note)
                if r.exam:
                    bits.append(f"考试要求 {r.exam}")
                    if r.exam_score:
                        bits.append(f"≥ {r.exam_score}")
                    if r.exam_note:
                        bits.append(r.exam_note)
                if r.gpa_min:
                    bits.append(f"成绩要求均分 ≥ {r.gpa_min}")
                    if r.gpa_note:
                        bits.append(r.gpa_note)
                if r.annual_cost:
                    bits.append(f"预估年成本约 {r.annual_cost} {r.cost_currency}")
                if p.deadline:
                    bits.append(f"申请截止：{p.deadline}")
                if p.eligibility:
                    bits.append("前置资格：" + "、".join(p.eligibility))
                if p.note:
                    bits.append(p.note)
                self._chunks.append(Chunk(
                    school=s.name, country=s.country, qs_rank=s.qs_rank,
                    text="。".join(bits),
                ))

    @property
    def size(self) -> int:
        return len(self._chunks)

    def _school_key(self, name: str) -> str:
        return name.lower()

    def _chunk_doc(self, c: Chunk) -> str:
        """把片段扩展为含别名/同义词的可匹配文档。"""
        parts = [c.school, c.text]
        for en, aliases in SCHOOL_ALIAS.items():
            if self._school_key(c.school) == en:
                parts.extend(aliases)
        # 国家别名
        for cn_name, syms in COUNTRY_ALIAS.items():
            if c.country == cn_name or c.country in syms or syms[0] in c.country:
                parts.extend(syms)
        # 线路标签
        if "高考" in c.text or "国内高考" in c.text:
            parts += ["高考", "gaokao"]
        if "alevel" in c.text.lower() or "a-level" in c.text.lower():
            parts += ["alevel", "al", "a水准"]
        if "雅思" in c.text:
            parts.append("ielts")
        if "托福" in c.text:
            parts.append("toefl")
        return " ".join(parts).lower()

    def retrieve(self, query: str, top_k: int = 6,
                 country: str = "", route: str = "",
                 school_filter: str = "") -> List[Chunk]:
        ql = query.lower()
        q_words = self._tokenize(query)
        # 归一化 query 别名
        ql_norm = ql
        for en, aliases in SCHOOL_ALIAS.items():
            for a in aliases:
                if a.lower() in ql:
                    ql_norm += " " + en
        scored: List[Chunk] = []
        for c in self._chunks:
            if country and not self._country_match(c.country, country):
                continue
            if school_filter and not self._school_match(c.school, school_filter):
                continue
            if route and route not in c.text.lower():
                continue
            doc = self._chunk_doc(c)
            score = 0.0
            for w in q_words:
                if w in doc:
                    score += 2.0
            # 命中任一学校别名 -> 强加分
            if any((a.lower() in ql) and (a.lower() in doc) for en_lst in SCHOOL_ALIAS.values()
                   for a in en_lst):
                score += 4.0
            # 校名精准
            if c.school.lower() in ql_norm:
                score += 6.0
            if c.school.lower() in ql:
                score += 6.0
            # 国家同义命中
            if any(a.lower() in ql and a.lower() in doc
                   for syms in COUNTRY_ALIAS.values() for a in syms):
                score += 3.0
            # 需求词命中
            if any(any(a.lower() in ql for a in grp) and
                   any(a.lower() in doc for a in grp)
                   for grp in REQ_ALIAS.values()):
                score += 1.5
            if score > 0:
                c.score = score
                scored.append(c)
        scored.sort(key=lambda x: (-x.score, x.qs_rank))
        return scored[:top_k]

    def _country_match(self, c_country: str, target: str) -> bool:
        t = target.lower()
        if c_country.lower() == t:
            return True
        for syms in COUNTRY_ALIAS.values():
            if t in [s.lower() for s in syms] and \
               (c_country in syms or syms[0].lower() in c_country.lower()):
                return True
        return False

    def _school_match(self, c_school: str, target: str) -> bool:
        t = target.lower()
        if t in c_school.lower():
            return True
        for en, aliases in SCHOOL_ALIAS.items():
            if en == c_school.lower() and t in [a.lower() for a in aliases]:
                return True
        return False

    def _tokenize(self, text: str) -> set:
        return set(re.findall(r"[a-z]{2,}", text.lower()))

    def school_profile(self, name: str) -> str:
        """给出某校所有线路的完整描述(供 LLM 上下文)。"""
        s = self.catalog.get(name)
        if not s:
            return f"未收录 {name}"
        lines = [f"### {s.name} (QS {s.qs_rank}, {s.country})"]
        for p in s.paths:
            r = p.requirement
            head = f"- 线路[{ROUTE_LABEL.get(p.path_type, p.path_type)}] 难度={p.band}"
            reqs = []
            if r.language_required:
                reqs.append(f"语言 {r.language_required}≥{r.language_score}"
                            + (f"({r.language_note})" if r.language_note else ""))
            if r.exam:
                reqs.append(f"{r.exam}≥{r.exam_score}"
                            + (f"({r.exam_note})" if r.exam_note else ""))
            if r.gpa_min:
                reqs.append(f"均分≥{r.gpa_min}")
            if r.annual_cost:
                reqs.append(f"约{r.annual_cost}{r.cost_currency}/年")
            if p.eligibility:
                reqs.append("资格:" + ",".join(p.eligibility))
            lines.append(head + ("｜" + "｜".join(reqs) if reqs else ""))
            if p.note:
                lines.append("  " + p.note)
        return "\n".join(lines)
