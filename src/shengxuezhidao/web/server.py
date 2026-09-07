"""轻量 HTTP/Web 查询服务(基于标准库, 零第三方依赖)。

将本体的核心能力暴露为 REST API, 便于前端/脚本"便捷查询":
  GET  /health        -> 服务健康检查
  GET  /stats         -> 资料库统计
  GET  /routes        -> 可选升学路径线路说明
  GET  /search        -> 多维检索(国家/QS分段/专业/线路/关键词/预算)
  POST /search        -> 同上, 支持更全参数
  POST /recommend     -> 学生画像坍缩推荐(低门槛偏好)
  POST /ask           -> 知识库问答/二次询问(可接 LLM)
  GET  /ask?q=...     -> 同上(简化用法)

用法:
  python -m shengxuezhidao serve [--host 127.0.0.1] [--port 8000]

说明:
  - 所有请求/响应均为 JSON(utf-8)。
  - 已加 CORS 头, 便于浏览器前端直接跨域调用。
  - 用 Python 标准库实现, 无需安装 Flask。
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from ..core.catalog import Catalog
from ..core.models import StudentProfile
from ..data.seed import load_seed
from ..engine.matcher import (
    collapse,
    format_recommendation,
    search as engine_search,
    SearchQuery,
)
from ..engine.rules import ROUTE_RULES, ROUTE_LABEL

VERSION = "0.1.0"


# ---------------------------------------------------------------- 序列化工具
def _path_req_dict(req) -> dict:
    return {
        "language_required": req.language_required,
        "language_score": req.language_score,
        "language_note": req.language_note,
        "exam": req.exam,
        "exam_score": req.exam_score,
        "exam_note": req.exam_note,
        "gpa_min": req.gpa_min,
        "gpa_note": req.gpa_note,
        "annual_cost": req.annual_cost,
        "cost_currency": req.cost_currency,
        "note": req.note,
    }


def _path_dict(p) -> dict:
    return {
        "path_type": p.path_type,
        "path_name": p.path_name,
        "applicable_countries": list(p.applicable_countries),
        "band": p.band,
        "eligibility": list(p.eligibility),
        "deadline": p.deadline,
        "note": p.note,
        "requirement": _path_req_dict(p.requirement),
    }


def _school_dict(s) -> dict:
    return {
        "name": s.name,
        "country": s.country,
        "region": s.region,
        "qs_rank": s.qs_rank,
        "qs_part": s.qs_part,
        "fields": list(s.fields),
        "city": s.city,
        "tuition_currency": s.tuition_currency,
        "available_routes": [
            ROUTE_LABEL.get(pt, pt) for pt in s.available_routes()
        ],
        "paths": [_path_dict(p) for p in s.paths],
    }


# ---------------------------------------------------------------- 数据访问
class _App:
    """持有共享的 Catalog 与问答依赖, 供 handler 调用。"""

    def __init__(self):
        self.catalog = Catalog()
        load_seed(self.catalog)

    def build_assistant(self, **llm_kwargs):
        from ..ai import Assistant
        from ..ai.kb import KnowledgeBase
        return Assistant(KnowledgeBase(self.catalog), **llm_kwargs)

    # ---- 业务动作, 均返回可 JSON 化的 dict ----
    def stats(self) -> dict:
        by_country: Dict[str, int] = {}
        by_route: Dict[str, int] = {}
        qs_parts: Dict[str, int] = {}
        for s in self.catalog.all():
            by_country[s.country] = by_country.get(s.country, 0) + 1
            qs_parts[s.qs_part] = qs_parts.get(s.qs_part, 0) + 1
            for pt in s.available_routes():
                by_route[ROUTE_LABEL.get(pt, pt)] = \
                    by_route.get(ROUTE_LABEL.get(pt, pt), 0) + 1
        return {
            "total_schools": self.catalog.size,
            "by_country": dict(sorted(by_country.items(), key=lambda x: -x[1])),
            "by_qs_part": qs_parts,
            "by_route": dict(sorted(by_route.items(), key=lambda x: -x[1])),
        }

    def routes(self) -> List[dict]:
        return [
            {"key": k, "label": v["label"], "note": v["note"]}
            for k, v in ROUTE_RULES.items()
        ]

    def search(self, q: SearchQuery) -> dict:
        res = engine_search(self.catalog, q)
        return {
            "total": len(res),
            "results": [
                {
                    "school": _school_dict(r.school),
                    "matched_path_types": [
                        ROUTE_LABEL.get(p.path_type, p.path_type)
                        for p in r.matched_paths
                    ],
                }
                for r in res
            ],
        }

    def recommend(self, profile: StudentProfile, top_k: int = 8,
                  qs_filter: Optional[str] = None) -> dict:
        from ..engine.matcher import Recommendation
        recs = collapse(profile, self.catalog, top_k=top_k,
                        qs_filter=qs_filter)
        return {
            "total": len(recs),
            "profile": {
                "education_route": profile.education_route,
                "language_score": profile.language_score,
                "budget": profile.max_budget,
                "pref_countries": list(profile.pref_countries),
                "want_low_threshold": profile.want_low_threshold,
            },
            "recommendations": [
                {
                    "rank": i + 1,
                    "school": _school_dict(r.school),
                    "path": _path_dict(r.path),
                    "route_label": ROUTE_LABEL.get(r.path.path_type,
                                                   r.path.path_type),
                    "band": r.path.band,
                    "score": r.score,
                    "summary": format_recommendation(r),
                }
                for i, r in enumerate(recs)
            ],
        }

    def ask(self, question: str, country: str = "",
            llm_kwargs: Optional[dict] = None) -> dict:
        asst = self.build_assistant(**(llm_kwargs or {}))
        ans = asst.ask(question, country=country)
        return {
            "question": question,
            "answer": ans.text,
            "source": ans.source,
            "engine": asst.source_label,
            "evidence": [c.text for c in ans.evidence[:8]],
            "error": ans.error or "",
        }

    def clarify(self, profile: StudentProfile) -> List[str]:
        return self.build_assistant().clarify(profile)


# ---------------------------------------------------------------- 请求解析
def _qs_to_str(q, key: str, default: str = "") -> str:
    vals = q.get(key)
    if not vals:
        return default
    return vals[0] if isinstance(vals, list) else str(vals)


def _query_from_params(d: dict) -> SearchQuery:
    """从 GET query 或 POST body 构造 SearchQuery。"""
    return SearchQuery(
        country=_clean(d.get("country")),
        qs_part=_clean(d.get("qs_part") or d.get("rank")),
        keyword=_clean(d.get("keyword")),
        field=_clean(d.get("field")),
        route=_clean(d.get("route")),
        max_cost=_opt_float(d.get("max_cost") or d.get("budget")),
    )


def _profile_from_params(d: dict) -> StudentProfile:
    """从 POST body 构造学生画像(坍缩推荐)。"""
    return StudentProfile(
        nationality=d.get("nationality") or "CN",
        education_route=d.get("route") or d.get("education_route") or "",
        language_score=_opt_float(d.get("language_score") or d.get("ielts")),
        language_type=(d.get("language_type") or "IELTS").upper(),
        gpa=_opt_float(d.get("gpa")),
        pref_countries=_clean_list(d.get("pref_countries") or d.get("countries")),
        pref_majors=_clean_list(d.get("pref_majors") or d.get("majors")),
        max_budget=_opt_float(d.get("max_budget") or d.get("budget")),
        want_low_threshold=_opt_bool(d.get("want_low_threshold") or d.get("low")),
    )


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return []


def _opt_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _opt_bool(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "yes", "y", "on")


# ---------------------------------------------------------------- HTTP Handler
def _json_body(handler):
    """读取请求体并解析为 dict(失败返回空 dict)。"""
    try:
        length = int(handler.headers.get("Content-Length", 0) or 0)
    except ValueError:
        length = 0
    if length <= 0:
        return {}
    try:
        raw = handler.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def make_handler(app: Optional[_App] = None):
    """根据共享的 _App 生成一个 handler 类。

    app 允许在模块内共享同一份 Catalog(内存热缓存), 避免每次请求重复加载。
    """
    shared = app if app is not None else _App()

    class Handler(BaseHTTPRequestHandler):
        # 关闭默认日志噪音, 保持服务干净
        def log_message(self, *args):
            pass

        # ---- CORS 与基础 ----
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods",
                             "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, Authorization")
            self.send_header("Content-Type", "application/json; charset=utf-8")

        def _send(self, code: int, payload: dict, pretty: bool = False):
            body = json.dumps(payload, ensure_ascii=False,
                              indent=2 if pretty else None).encode("utf-8")
            self.send_response(code)
            self._cors()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _ok(self, data, **meta):
            payload = {"ok": True, **meta, "data": data}
            self._send(200, payload)

        def _err(self, code: int, msg: str):
            self._send(code, {"ok": False, "error": msg})

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            self._route(method="GET")

        def do_POST(self):
            self._route(method="POST")

        # ---- 路由 ----
        def _route(self, method):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            params = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
            # 合并 query 与 body(GET 只读 query, POST 读 body)
            data = params.copy()
            if method == "POST":
                body = _json_body(self)
                # query 参数优先, body 兜底
                data = {**body, **params}

            try:
                if path == "/health":
                    self._ok({"service": "shengxuezhidao",
                              "version": VERSION,
                              "status": "ok",
                              "schools": shared.catalog.size})
                elif path == "/stats":
                    self._ok(shared.stats())
                elif path == "/routes":
                    self._ok(shared.routes())
                elif path == "/search":
                    self._handle_search(data)
                elif path == "/recommend":
                    self._handle_recommend(data)
                elif path == "/ask":
                    self._handle_ask(data)
                elif path == "/llm-config":
                    self._handle_llm_config()
                else:
                    self._err(404, f"未知路径: {path}")
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                self._err(500, f"服务内部错误: {type(e).__name__}: {e}")

        # ---- 各业务端点 ----
        def _handle_search(self, data):
            q = _query_from_params(data)
            result = shared.search(q)
            self._ok(result["results"], total=result["total"])

        def _handle_recommend(self, data):
            profile = _profile_from_params(data)
            top_k = int(_opt_float(data.get("top") or 8) or 8)
            qs_filter = _clean(data.get("qs_filter") or data.get("rank"))
            result = shared.recommend(profile, top_k=top_k, qs_filter=qs_filter)
            # 若未坍缩出方案, 顺带返回二次询问问题
            extra = {}
            if result["total"] == 0:
                extra["clarify"] = shared.clarify(profile)
            self._ok(result, **extra)

        def _handle_ask(self, data):
            question = _clean(data.get("question") or data.get("q"))
            if not question:
                self._err(400, "缺少问题参数(question 或 q)")
                return
            llm_kwargs = {}
            for key, arg in (("api_key", "api_key"),
                             ("base_url", "base_url"),
                             ("model", "model"),
                             ("provider", "provider"),
                             ("timeout", "timeout")):
                val = data.get(arg)
                if val is not None and val != "":
                    llm_kwargs[key] = _opt_float(val) if key == "timeout" else str(val)
            no_llm = _opt_bool(data.get("no_llm"))
            if no_llm:
                llm_kwargs["api_key"] = ""
                llm_kwargs["provider"] = ""
            result = shared.ask(question, country=_clean(data.get("country")) or "",
                                llm_kwargs=llm_kwargs)
            self._ok({
                "question": result["question"],
                "answer": result["answer"],
                "source": result["source"],
                "engine": result["engine"],
                "evidence": result["evidence"],
                "error": result["error"],
            })

        def _handle_llm_config(self):
            from ..ai import LLMConfig, KNOWN_PROVIDERS, DEFAULT_PROVIDER
            cfg = LLMConfig.load()
            self._ok({
                "provider": cfg.provider or "(默认)",
                "base_url": cfg.base_url,
                "model": cfg.model,
                "api_key_configured": bool(cfg.api_key),
                "llm_enabled": bool(cfg.effective_enabled and cfg.api_key),
                "known_providers": KNOWN_PROVIDERS,
                "default_provider": DEFAULT_PROVIDER,
            })

    return Handler


# ---------------------------------------------------------------- 启动入口
def serve(host: str = "127.0.0.1", port: int = 8000,
          app: Optional[_App] = None) -> ThreadingHTTPServer:
    """启动 HTTP 服务(阻塞)。返回 server 实例。

    会做端口占用自检: 若端口被占用抛 OSError, 便于 CLI 提示换端口。
    """
    handler = make_handler(app)
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    return httpd
