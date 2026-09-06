"""命令行交互入口。

用法示例:
  python -m shengxuezhidao search --country 英国 --route alevel
  python -m shengxuezhidao recommend --route alevel --ielts 7.0 --budget 400000
  python -m shengxuezhidao ask "曼彻斯特大学高考要多少分?"
  python -m shengxuezhidao ask "澳洲哪些学校接受高考" --api-key sk-xxx
  python -m shengxuezhidao llm-config          # 查看/生成当前 LLM 接入配置
  python -m shengxuezhidao stats
"""
from __future__ import annotations

import argparse
import sys

from ..core.catalog import Catalog
from ..core.models import ScoreBand, StudentProfile
from ..data.seed import load_seed
from ..engine.matcher import (
    collapse,
    format_recommendation,
    search as engine_search,
    SearchQuery,
)
from ..engine.rules import ROUTE_RULES, ROUTE_LABEL
from . import interactive


def _catalog() -> Catalog:
    c = Catalog()
    load_seed(c)
    return c


def _add_recommend_args(sp):
    sp.add_argument("--route", default="alevel", help="教育路线 gaokao/ap/alevel/ib")
    sp.add_argument("--ielts", type=float, default=6.5, help="已有雅思分数")
    sp.add_argument("--gpa", type=float, default=None, help="均分(百分制)")
    sp.add_argument("--budget", type=float, default=None, help="年预算(人民币)")
    sp.add_argument("--countries", nargs="*", default=[], help="偏好国家")
    sp.add_argument("--low", action="store_true", help="倾向相对低门槛方案")
    sp.add_argument("--top", type=int, default=8)


def _add_llm_args(sp):
    """在支持 LLM 的子命令上增加可选接入参数。"""
    g = sp.add_argument_group("LLM 接入(可选, 覆盖环境变量)")
    g.add_argument("--api-key", default=None, help="API 密钥(默认读 SXZD_LLM_API_KEY)")
    g.add_argument("--base-url", default=None, help="API 地址(默认 DeepSeek)")
    g.add_argument("--model", default=None, help="模型名(默认 deepseek-chat)")
    g.add_argument("--provider", default=None,
                   help="提供商预设: deepseek/openai/qwen/glm/ollama/moonshot/siliconflow")
    g.add_argument("--timeout", type=int, default=None, help="请求超时(秒)")
    g.add_argument("--no-llm", action="store_true", help="强制使用本地检索(禁用LLM)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shengxuezhidao",
        description="全球 Top500 大学升学智能查询系统本体")
    sub = p.add_subparsers(dest="cmd")

    # search
    sp = sub.add_parser("search", help="多维检索学校")
    sp.add_argument("--country", default=None)
    sp.add_argument("--rank", default=None,
                    choices=["top10", "top50", "top100", "top200", "top500"])
    sp.add_argument("--field", default=None, help="学科方向")
    sp.add_argument("--route", default=None, help="线路 gaokao/ap/alevel/ib")
    sp.add_argument("--keyword", default="")
    sp.add_argument("--max-cost", type=float, default=None)

    # recommend (坍缩)
    sp = sub.add_parser("recommend", help="学生画像坍缩推荐")
    _add_recommend_args(sp)

    # ask (知识库问答)
    sp = sub.add_parser("ask", help="AI 知识库问答/二次询问")
    sp.add_argument("question", nargs="?", help="问题, 缺省进入交互")
    sp.add_argument("--country", default=None)
    _add_llm_args(sp)

    # llm-config (查看 LLM 接入配置)
    sp = sub.add_parser("llm-config",
                        help="查看 LLM 接入配置 / 生成接入说明")
    sp.add_argument("--env", action="store_true",
                    help="输出可复制粘贴的环境变量配置示例")

    # stats
    sub.add_parser("stats", help="资料库统计")

    # routes
    sub.add_parser("routes", help="查看可选升学路径线路说明")

    # update (自动更新/同步)
    sp = sub.add_parser("update", help="从数据源同步(自动更新)")
    sp.add_argument("source", nargs="?", default=None,
                    help="数据源路径(JSON 文件或目录); 缺省打印说明")
    sp.add_argument("--export", default=None, help="同步后导出库到该 JSON 文件")
    sp.add_argument("--dry-run", action="store_true", help="仅比对不合并")

    # export
    sp = sub.add_parser("export", help="导出资料库为 JSON(便于归档/增量同步)")
    sp.add_argument("out", default="data/schools.json", nargs="?")

    return p


def _make_assistant(no_llm: bool = False, api_key=None, base_url=None,
                    model=None, provider=None, timeout=None):
    """创建 Assistant, 支持从 args 覆盖 LLM 配置。"""
    from ..ai import Assistant
    from ..ai.kb import KnowledgeBase
    c = _catalog()
    kb = KnowledgeBase(c)
    kwargs = {}
    if api_key is not None:
        kwargs["api_key"] = api_key
    if base_url is not None:
        kwargs["base_url"] = base_url
    if model is not None:
        kwargs["model"] = model
    if provider is not None:
        kwargs["provider"] = provider
    if timeout is not None:
        kwargs["timeout"] = timeout
    if no_llm:
        kwargs["api_key"] = ""   # 强制禁用 LLM
        kwargs["provider"] = ""
    return Assistant(kb, **kwargs)


def cmd_search(args) -> int:
    c = _catalog()
    q = SearchQuery(country=args.country, qs_part=args.rank, field=args.field,
                    route=args.route, keyword=args.keyword, max_cost=args.max_cost)
    res = engine_search(c, q)
    if not res:
        print("未检索到匹配学校, 尝试放宽条件。")
        return 0
    print(f"命中 {len(res)} 所学校:")
    for r in res:
        ptypes = "、".join(ROUTE_LABEL.get(pt, pt) for pt in r.school.available_routes())
        print(f"  • {r.school.name} | QS {r.school.qs_rank} | {r.school.country} "
              f"| 线路:{ptypes} | 强项:{','.join(r.school.fields)}")
        for p in r.matched_paths:
            req = p.requirement
            detail = []
            if req.language_required and req.language_score:
                detail.append(f"{req.language_required}≥{req.language_score}")
            if req.exam and (req.exam_score or req.exam_note):
                detail.append(req.exam + (str(req.exam_score) if req.exam_score else "") +
                              (" " + req.exam_note if req.exam_note else ""))
            if detail:
                print(f"      - [{ROUTE_LABEL.get(p.path_type, p.path_type)}] "
                      f"难度:{p.band} " + " / ".join(detail))
    return 0


def cmd_recommend(args) -> int:
    c = _catalog()
    prof = StudentProfile(
        nationality="CN",
        education_route=args.route,
        location="中国" if args.route != "overseas_highschool" else "美国",
        language_score=args.ielts,
        language_type="IELTS",
        gpa=args.gpa,
        pref_countries=args.countries,
        max_budget=args.budget,
        want_low_threshold=args.low,
    )
    recs = collapse(prof, c, top_k=args.top)
    if not recs:
        print("根据当前画像未坍缩出可行方案, 请补充信息或用 --low 放宽。")
        # 提示追问
        asst = _make_assistant()
        print("\n建议补充以下信息(二次询问):")
        for q in asst.clarify(prof):
            print("  - " + q)
        return 0
    print(f"根据你的画像(线路:{ROUTE_LABEL.get(args.route, args.route)}"
          f", IELTS {args.ielts}) 推荐(按可行性排序):\n")
    for i, r in enumerate(recs, 1):
        print(f"[{i}] " + format_recommendation(r))
    return 0


def cmd_ask(args) -> int:
    from ..ai import LLMConfig

    asst = _make_assistant(
        no_llm=args.no_llm,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        provider=args.provider,
        timeout=args.timeout,
    )
    # 打印当前引擎状态
    state = asst.source_label
    if not asst.llm_ready:
        hint = ("强制本地检索模式。" if args.no_llm
                else "设置 SXZD_LLM_API_KEY 或使用 --api-key 接入 LLM。")
        print(f"[当前: {state}] {hint}\n")
    if args.question:
        ans = asst.ask(args.question, country=args.country or "")
        print(ans.pretty)
        return 0
    print(f"[问答引擎: {state}] 输入 exit 退出\n")
    interactive.ask_loop(asst)
    return 0


def cmd_llm_config(args) -> int:
    """查看/输出 LLM 接入配置。"""
    from ..ai import LLMConfig, KNOWN_PROVIDERS, DEFAULT_PROVIDER

    cfg = LLMConfig.load()
    print("=== LLM 接入配置 ===")
    print(f"提供商(provider): {cfg.provider or '(默认)'}")
    print(f"API 地址(base_url): {cfg.base_url}")
    print(f"模型(model): {cfg.model}")
    print(f"API Key: {'✅ 已配置 (sk-' + cfg.api_key[-4:] + ')' if cfg.api_key else '❌ 未配置'}")
    print(f"超时: {cfg.timeout}s | 最大生成: {cfg.max_tokens} tokens | 温度: {cfg.temperature}")
    print(f"LLM 启用: {'✅' if cfg.effective_enabled else '❌ (无 Key, 走本地检索)'}")

    if args.env:
        print("\n--- 可复制到 shell 的环境变量 ---")
        print(f"export SXZD_LLM_API_KEY={cfg.api_key or 'sk-你的密钥'}")
        print(f"export SXZD_LLM_BASE_URL={cfg.base_url}")
        print(f"export SXZD_LLM_MODEL={cfg.model}")
        if cfg.provider:
            print(f"export SXZD_LLM_PROVIDER={cfg.provider}")

    print(f"\n内置 provider 预设:")
    for name, conf in KNOWN_PROVIDERS.items():
        mark = " ◀ 当前" if name == cfg.provider else ""
        print(f"  - {name}: base_url={conf['base_url']}, model={conf['model']}{mark}")

    print("\n更多自定义: 参见 README「AI 接入配置」章节。")
    return 0


def cmd_stats(args) -> int:
    c = _catalog()
    print(f"资料库学校总数: {c.size}")
    by_country: dict = {}
    for s in c.all():
        by_country[s.country] = by_country.get(s.country, 0) + 1
    for k, v in sorted(by_country.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} 所")
    return 0


def cmd_routes(args) -> int:
    print("可选升学路径线路(同一大学可并存多线路):\n")
    for k, v in ROUTE_RULES.items():
        print(f"  [{k}] {v['label']} - {v['note']}")
    return 0


def cmd_update(args) -> int:
    from ..data.updater import JsonSource, OfficialManualSource, sync_catalog
    from pathlib import Path
    if not args.source:
        print("自动更新说明:")
        print("  - 数据源: 官方/授权 JSON(与种子格式一致)或目录;")
        print("  - 用法: python -m shengxuezhidao update <data_dir_or_file> "
              "[--export out.json] [--dry-run]")
        print("  - 建议: 定时任务把官网抓取产物落地为 JSON, 再执行本命令幂等合并。")
        return 0
    pth = Path(args.source)
    source = (OfficialManualSource(args.source) if pth.is_dir()
              else JsonSource(args.source))
    c = _catalog()
    stat = sync_catalog(c, source, dry_run=args.dry_run)
    print(f"同步完成: 抓取 {stat['fetched']} 条, "
          f"新增 {stat['added']}, 更新 {stat['updated']}, 无变化 {stat['unchanged']}"
          + (" (dry-run, 未实际合并)" if args.dry_run else ""))
    if args.export:
        c.save_json(args.export)
        print(f"已导出到 {args.export}, 库共 {c.size} 所。")
    return 0


def cmd_export(args) -> int:
    c = _catalog()
    n = c.save_json(args.out)
    print(f"已导出 {n} 所学校到 {args.out}")
    return 0


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 0
    table = {
        "search": cmd_search,
        "recommend": cmd_recommend,
        "ask": cmd_ask,
        "llm-config": cmd_llm_config,
        "stats": cmd_stats,
        "routes": cmd_routes,
        "update": cmd_update,
        "export": cmd_export,
    }
    return table[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
