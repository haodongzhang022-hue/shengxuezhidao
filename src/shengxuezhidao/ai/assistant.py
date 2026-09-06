"""AI 助手: 带知识库的二次询问与自然语言问答。

形态:
- 先通过 KnowledgeBase 检索相关片段(检索增强, RAG)
- 默认内置一个"检索即答"的确定性回答器(无需任何外部服务即可跑通演示)
- 若配置了 SXZD_LLM_API_KEY, 可选用 OpenAI 兼容接口做生成式回答
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from ..core.models import StudentProfile
from .kb import Chunk, KnowledgeBase, REQ_ALIAS, COUNTRY_ALIAS


@dataclass
class Answer:
    text: str
    evidence: List[Chunk] = field(default_factory=list)
    source: str = "local-retrieval"   # local-retrieval | llm

    @property
    def pretty(self) -> str:
        out = [self.text]
        if self.evidence:
            out.append("\n[依据] " + self.evidence[0].text[:150]
                       + (" …" if len(self.evidence[0].text) > 150 else ""))
        return "\n".join(out)


class Assistant:
    """面向学生的一次/二次追问的问答助手。"""

    def __init__(self, kb: KnowledgeBase, model: Optional[str] = None):
        self.kb = kb
        self.model = model or os.getenv("SXZD_LLM_MODEL", "")
        self.api_key = os.getenv("SXZD_LLM_API_KEY", "")
        self.base_url = os.getenv("SXZD_LLM_BASE_URL", "")
        self._openai = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._openai = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url or None,
                )
            except Exception:
                self._openai = None

    # ------------------------------------------------------------ 主问答
    _COUNTRY_HINT = ["英国", "美国", "澳洲", "澳大利亚", "加拿大", "新加坡",
                    "香港", "日本", "韩国", "新西兰", "爱尔兰", "德国", "法国"]

    def _detect_country(self, question: str) -> str:
        for name, syms in COUNTRY_ALIAS.items():
            for a in syms:
                if a and a.lower() in question.lower():
                    return name
        return ""

    def ask(self, question: str, profile: Optional[StudentProfile] = None,
            country: str = "", top_k: int = 8) -> Answer:
        if not country:
            country = self._detect_country(question)
        evidence = self.kb.retrieve(question, top_k=top_k, country=country)
        context = ""
        if profile is not None:
            context += self._profile_text(profile) + "\n"
        context += "\n".join(c.text for c in evidence)

        if self._openai is not None:
            try:
                return self._ask_llm(question, context, evidence)
            except Exception:
                pass
        return Answer(text=self._local_answer(question, evidence),
                      evidence=evidence, source="local-retrieval")

    # ------------------------------------------------------------ 检索即答
    def _local_answer(self, question: str, evidence: List[Chunk]) -> str:
        if not evidence:
            return ("知识库暂未检索到与提问相关的学校数据。请补充目标学校名、国家或 "
                    "线路(高考/AP/A-Level/IB/海外高中), 或先执行数据收录更新。")
        q = question.lower()

        # A) 问"哪些学校/国家" -> 汇总列表
        if any(k in question for k in ("哪些", "有哪些", "哪个", "什么学校")):
            # 找被问的线路
            asked_route = None
            if any(a in q for a in ("高考", "gaokao")):
                asked_route = "高考"
            elif any(a in q for a in ("alevel", "al")):
                asked_route = "A-Level"
            elif any(a in q for a in ("ap",)):
                asked_route = "AP"
            # 汇总去重学校
            lines, seen = [], set()
            for c in evidence:
                # 排除"不接受/不看"等负面表达造成的误命中
                if asked_route and (asked_route not in c.text or
                                    ("不看" in c.text and asked_route in c.text
                                     and "高考成绩" not in c.text and "考试要求 高考" not in c.text)):
                    continue
                if c.school in seen:
                    continue
                seen.add(c.school)
                # 仅展示含该线路的片段, 去掉路径前缀
                seg = c.text
                for rname in ("A-Level", "AP 课程", "IB 文凭", "国内高考"):
                    if rname in seg:
                        seg = seg.split("」", 1)[-1]
                        break
                lines.append(f"▸ {c.school} (QS {c.qs_rank}, {c.country}): {seg[:100]}")
            if not lines:
                lines = [f"▸ {c.school} (QS {c.qs_rank}, {c.country})"
                         for c in evidence]
            return ("为你汇总相关学校如下(可再追问具体要求):\n" + "\n".join(lines))

        # B) 问某校"要求/条件/分数/雅思"
        if any(k in question for k in ("要求", "条件", "门槛", "分数", "雅思",
                                       "托福", "gpa", "sat", "多少", "需要",
                                       "怎么申请", "怎么去")):
            # 识别被问的具体线路(高考/AP/A-Level), 用于优先聚焦对应片段
            focus_route = None
            if any(a in q for a in ("高考", "gaokao", "国内高考")):
                focus_route = "高考"
            elif any(a in q for a in ("alevel", "a level", "a水准", "al ")):
                focus_route = "A-Level"
            elif any(a in q for a in ("ap",)) and not any(a in q for a in ("gap", "sat")):
                focus_route = "AP"
            focused = [c for c in evidence
                       if focus_route is None or focus_route in c.text]
            if not focused:
                focused = evidence
            lines, seen = [], set()
            for c in focused:
                if c.school in seen:
                    continue
                seen.add(c.school)
                short = c.text
                lines.append(f"▸ {c.school}: {short}")
            if not lines:
                for c in evidence[:3]:
                    lines.append(f"▸ {c.school}: {c.text}")
            return ("为你查到相关入学要求如下(标注以官方最新为准):\n" + "\n".join(lines))

        # C) 学校名直接提问
        if any(a.lower() in q for en_lst in [
                ["imperial college london", "帝国理工"], ["剑桥"],
                ["曼彻斯特", "曼大"], ["爱丁堡"], ["墨尔本"], ["悉尼"],
                ["多伦多"], ["香港大学", "港大"], ["新加坡国立"]] for a in en_lst):
            top = evidence[0]
            return (f"关于 {top.school} (QS {top.qs_rank}, {top.country}): {top.text}")
        return ("基于知识库匹配到以下相关信息：\n" +
                "\n".join(f"▸ {c.school}: {c.text}" for c in evidence[:3]))

    def _ask_llm(self, question, context, evidence) -> Answer:
        sys_prompt = (
            "你是资深国际升学顾问。请仅依据给定知识库上下文回答, 不要编造未收录的数据。"
            "若上下文不足请明确说明需补充哪些信息, 并可给出进一步追问(二次询问)。"
            "回答用中文, 简洁有条理。"
        )
        resp = self._openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content":
                 f"【知识库上下文】\n{context}\n\n【学生问题】{question}"},
            ],
            temperature=0.2,
        )
        return Answer(text=resp.choices[0].message.content.strip(),
                      evidence=evidence, source="llm")

    # ------------------------------------------------------------ 追问流程
    def clarify(self, profile: StudentProfile) -> List[str]:
        """二次询问: 根据画像缺什么返回需要向学生追问的问题清单。"""
        qs = []
        if not profile.education_route:
            qs.append("你目前的课程体系是？国内高考 / AP / A-Level / IB / 海外高中?")
        if profile.language_score is None:
            qs.append("你目前的英语成绩(IELTS/TOEFL 分数)是多少? 若还没考请说明。")
        if not profile.pref_countries:
            qs.append("你倾向去哪些国家? (如英国/美国/澳洲/加拿大/新加坡/港澳)")
        if not profile.pref_majors:
            qs.append("想申请什么专业方向?")
        if profile.max_budget is None:
            qs.append("家庭每年预算大概是多少(人民币)?")
        return qs

    def _profile_text(self, p: StudentProfile) -> str:
        return (f"学生画像: 国籍={p.nationality}, 课程={p.education_route or '未知'}, "
                f"语言={p.language_type}={p.language_score}, "
                f"GPA={p.gpa}, 偏好国家={p.pref_countries}, "
                f"偏好专业={p.pref_majors}, 预算上限={p.max_budget}, "
                f"倾向低门槛={p.want_low_threshold}")
