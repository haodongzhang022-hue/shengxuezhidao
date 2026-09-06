"""AI 助手: 带知识库的二次询问与自然语言问答。

形态:
- 先通过 KnowledgeBase 检索相关片段(检索增强, RAG)
- 默认内置一个"检索即答"的确定性回答器(无需任何外部服务即可跑通演示)
- 默认配置指向 DeepSeek API; 可通过环境变量/配置文件/构造参数切换为
  任意 OpenAI 兼容大模型(OpenAI / Qwen / GLM / Ollama 本地 / 自定义网关等)
- 无 api_key 或请求失败时自动回退到本地检索回答
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.models import StudentProfile
from .config import LLMConfig
from .kb import Chunk, KnowledgeBase, REQ_ALIAS, COUNTRY_ALIAS


@dataclass
class Answer:
    text: str
    evidence: List[Chunk] = field(default_factory=list)
    source: str = "local-retrieval"   # local-retrieval | llm
    error: str = ""                    # 若 LLM 调用出错, 记录错误信息

    @property
    def pretty(self) -> str:
        out = [self.text]
        if self.evidence:
            out.append("\n[依据] " + self.evidence[0].text[:150]
                       + (" …" if len(self.evidence[0].text) > 150 else ""))
        if self.error:
            out.append(f"\n[提示] {self.error}")
        return "\n".join(out)


class Assistant:
    """面向学生的一次/二次追问的问答助手。

    默认接入 DeepSeek; 可通过以下方式自定义:
      1. 构造参数: Assistant(kb, api_key=..., base_url=..., model=...)
      2. 环境变量: SXZD_LLM_API_KEY / SXZD_LLM_BASE_URL / SXZD_LLM_MODEL ...
      3. 配置文件: SXZD_LLM_CONFIG=<path> 指向一个 JSON
      4. 内置 provider 预设: provider="openai" / "qwen" / "glm" / "ollama" ...

    优先级: 构造参数 > 环境变量 > 配置文件 > 默认(DeepSeek)
    """

    def __init__(self, kb: KnowledgeBase, model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 provider: Optional[str] = None,
                 timeout: Optional[int] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None):
        self.kb = kb
        # 合并加载配置
        self._cfg = LLMConfig.load(
            api_key=api_key, base_url=base_url,
            model=model, provider=provider,
        )
        if timeout is not None:
            self._cfg.timeout = timeout
        if temperature is not None:
            self._cfg.temperature = temperature
        if max_tokens is not None:
            self._cfg.max_tokens = max_tokens

        # 尝试使用 openai SDK(若已安装); 否则用标准库 urllib 走 REST
        self._sdk_client = None
        if self._cfg.effective_enabled:
            try:
                from openai import OpenAI
                self._sdk_client = OpenAI(
                    api_key=self._cfg.api_key,
                    base_url=self._cfg.base_url,
                    timeout=self._cfg.timeout,
                    max_retries=1,
                )
            except Exception:
                self._sdk_client = None

    # ------------------------------------------------------------ 配置只读
    @property
    def config(self) -> LLMConfig:
        return self._cfg

    @property
    def llm_ready(self) -> bool:
        """是否具备发起 LLM 请求的条件。"""
        return self._cfg.effective_enabled and bool(self._cfg.api_key)

    @property
    def source_label(self) -> str:
        """描述当前问答引擎来源(便于用户确认)。"""
        if self.llm_ready:
            return f"llm({self._cfg.provider}/{self._cfg.model})"
        return "local-retrieval(未配置 API Key)"

    # ------------------------------------------------------------ 主问答
    def ask(self, question: str, profile: Optional[StudentProfile] = None,
            country: str = "", top_k: int = 8) -> Answer:
        if not country:
            country = self._detect_country(question)
        evidence = self.kb.retrieve(question, top_k=top_k, country=country)
        context = ""
        if profile is not None:
            context += self._profile_text(profile) + "\n"
        context += "\n".join(c.text for c in evidence)

        # 若配置了 LLM, 优先用 LLM 生成; 失败自动回退
        if self.llm_ready:
            try:
                return self._ask_llm(question, context, evidence)
            except Exception as e:
                err = f"LLM 调用失败({type(e).__name__}: {e}), 已回退本地检索回答。"
                return Answer(
                    text=self._local_answer(question, evidence),
                    evidence=evidence,
                    source="local-retrieval",
                    error=err,
                )
        return Answer(text=self._local_answer(question, evidence),
                      evidence=evidence, source="local-retrieval")

    # ------------------------------------------------------------ 检测国家
    _COUNTRY_HINT = ["英国", "美国", "澳洲", "澳大利亚", "加拿大", "新加坡",
                    "香港", "日本", "韩国", "新西兰", "爱尔兰", "德国", "法国"]

    def _detect_country(self, question: str) -> str:
        for name, syms in COUNTRY_ALIAS.items():
            for a in syms:
                if a and a.lower() in question.lower():
                    return name
        return ""

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

    # ------------------------------------------------------------ LLM 生成
    def _ask_llm(self, question: str, context: str,
                 evidence: List[Chunk]) -> Answer:
        """调用 LLM 生成回答。

        优先尝试已安装的 openai SDK; 若 SDK 不可用(未安装/初始化失败),
        则用标准库 urllib 直接调用 REST /chat/completions 接口。
        """
        sys_prompt = (
            "你是资深国际升学顾问。请仅依据给定知识库上下文回答, 不要编造未收录的数据。"
            "若上下文不足请明确说明需补充哪些信息, 并可给出进一步追问(二次询问)。"
            "回答用中文, 简洁有条理。"
        )

        if self._sdk_client is not None:
            resp = self._sdk_client.chat.completions.create(
                model=self._cfg.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content":
                     f"【知识库上下文】\n{context}\n\n【学生问题】{question}"},
                ],
                temperature=self._cfg.temperature,
                max_tokens=self._cfg.max_tokens,
            )
            text = resp.choices[0].message.content.strip()
        else:
            text = self._http_chat_completion(sys_prompt, context, question)

        return Answer(text=text, evidence=evidence, source="llm")

    def _http_chat_completion(self, sys_prompt: str, context: str,
                              question: str) -> str:
        """标准库 urllib 直连 OpenAI 兼容 /chat/completions 接口。"""
        url = self._cfg.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content":
                 f"【知识库上下文】\n{context}\n\n【学生问题】{question}"},
            ],
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._cfg.api_key}",
        }
        # 合并自定义 headers
        for k, v in self._cfg.headers.items():
            headers[k] = v

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise RuntimeError(
                f"HTTP {e.code}: {e.reason} - {detail}"
            ) from e

        try:
            return raw["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"响应格式异常: {json.dumps(raw, ensure_ascii=False)[:300]}"
            ) from e

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
