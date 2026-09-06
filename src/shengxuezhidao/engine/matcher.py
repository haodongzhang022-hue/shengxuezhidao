"""检索 + 学生画像坍缩匹配 + 低门槛推荐。

术语:
- "坍缩": 给定学生画像, 把全校全路径收敛到"该生实际可申请的
  路径子集", 并按可行性/偏好打分排序。
- 低门槛: 在候选集内优先推荐难度带更低、要求更易达成的路径。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.models import (
    BAND_RANK,
    AdmissionPath,
    School,
    ScoreBand,
    StudentProfile,
)
from .rules import student_route_candidates, ROUTE_LABEL


# ---------------------------------------------------------------- 检索
@dataclass
class SearchQuery:
    country: Optional[str] = None
    qs_part: Optional[str] = None      # top10/top50/top100/top200/top500
    keyword: str = ""                  # 校名/城市
    field: Optional[str] = None        # 学科/专业方向
    route: Optional[str] = None        # 指定路径线路
    max_cost: Optional[float] = None


@dataclass
class SearchResult:
    school: School
    matched_paths: List[AdmissionPath] = field(default_factory=list)


def search(catalog, q: SearchQuery) -> List[SearchResult]:
    out: List[SearchResult] = []
    q_part = (q.qs_part or "").lower()
    for s in catalog.all():
        if q.country and s.country.lower() != q.country.lower():
            continue
        if q_part and s.qs_part != q_part:
            # 允许按排名细分
            if not _qs_ok(s.qs_rank, q_part):
                continue
        if q.keyword:
            hay = (s.name + s.city + s.country + s.region).lower()
            if q.keyword.lower() not in hay:
                continue
        if q.field:
            if not any(q.field.lower() in f.lower() for f in s.fields):
                continue
        matched = list(s.paths)
        if q.route:
            p = s.path(q.route)
            matched = [p] if p else []
            if not matched:
                continue
        if q.max_cost is not None:
            keep = [p for p in matched if _cost_ok(p, q.max_cost)]
            matched = keep
            if not matched:
                continue
        out.append(SearchResult(school=s, matched_paths=matched))
    return out


def _qs_ok(rank: int, part: str) -> bool:
    if part == "top10":
        return 1 <= rank <= 10
    if part == "top50":
        return rank <= 50
    if part == "top100":
        return rank <= 100
    if part == "top200":
        return rank <= 200
    if part == "top500":
        return rank <= 500
    return True


def _cost_ok(p: AdmissionPath, budget: float) -> bool:
    c = p.requirement.annual_cost
    if c <= 0:
        return True  # 成本未知, 视为可(保守)
    # 若为外币成本, 简单按汇率粗略换算占位(实际应由配置化汇率计算)
    return c <= budget


# ---------------------------------------------------------------- 打分与坍缩
def _meet_score(profile: StudentProfile, p: AdmissionPath) -> bool:
    """该学生对这条路径的要求是否初步满足(宽松判据, 用于坍缩收敛)。"""
    r = p.requirement
    # 语言
    if r.language_score > 0 and profile.language_score is not None:
        if profile.language_type.upper() == "IELTS":
            if profile.language_score < r.language_score - 0.5:  # 容忍半档待提分
                return False
        else:  # TOEFL 之类
            if profile.language_score < r.language_score * 0.92:
                return False
    # GPA / 均分
    if r.gpa_min > 0 and profile.gpa is not None:
        if profile.gpa < r.gpa_min - 1.0:  # 容忍 1 分(百分制)
            return False
    return True


def _meet_budget(profile: StudentProfile, p: AdmissionPath) -> bool:
    if profile.max_budget is None:
        return True
    c = p.requirement.annual_cost
    if c <= 0:
        return True
    return c <= profile.max_budget


def _score_path(profile: StudentProfile, p: AdmissionPath,
                school: School) -> float:
    """路径可行性评分(越高越好)。用于坍缩后的排序。"""
    score = 0.0
    # 难度带: 越低门槛给分越高
    band_score = {
        ScoreBand.VERY_HARD: 0,
        ScoreBand.HARD: 2,
        ScoreBand.MEDIUM: 4,
        ScoreBand.REACHABLE: 6,
        ScoreBand.ACCESSIBLE: 8,
    }
    score += band_score.get(p.band, 3)

    # 偏好难度
    if profile.want_low_threshold:
        score += (8 - BAND_RANK.get(p.band, 4)) * 0.6  # 低门槛加成

    # 国家偏好
    if school.country.upper() in [c.upper() for c in profile.pref_countries]:
        score += 3
    # 学科偏好
    if any(profile.pref_majors) and school.fields:
        if any(pm.lower() in f.lower() for pm in profile.pref_majors
               for f in school.fields):
            score += 2
    # 排名加成(QS 越高越有含金量, 适度加成)
    rank_bonus = 0
    if school.qs_rank:
        rank_bonus = max(0.0, (200 - school.qs_rank) / 200.0)  # 0..1
    score += rank_bonus
    return round(score, 3)


def collapse_school(profile: StudentProfile, school: School,
                    candidate_routes: Optional[List[str]] = None
                    ) -> Optional[AdmissionPath]:
    """对单个学校做"坍缩": 返回该生在该校最可行的那条路径。

    若该校没有该生可走的路径, 或所有路径均不满足基本要求, 返回 None。
    """
    routes = candidate_routes or student_route_candidates(profile)
    feasible = []
    for r in routes:
        p = school.path(r)
        if p is None:
            continue
        # 国籍适用性
        if p.applicable_countries and \
           profile.nationality.upper() not in \
           [c.upper() for c in p.applicable_countries]:
            continue
        if not _meet_score(profile, p):
            continue
        if not _meet_budget(profile, p):
            continue
        feasible.append(p)
    if not feasible:
        return None
    # 选打分最高的一条作为该校坍缩结果
    return max(feasible, key=lambda p: _score_path(profile, p, school))


@dataclass
class Recommendation:
    school: School
    path: AdmissionPath
    score: float
    band_label: str = ""


def collapse(profile: StudentProfile, catalog, top_k: int = 15,
             qs_filter: Optional[str] = None) -> List[Recommendation]:
    """输入学生画像 -> 全校坍缩 -> 收敛出推荐候选集并排序。

    这是本体的核心智能(坍缩)入口。
    """
    candidate_routes = student_route_candidates(profile)
    results: List[Recommendation] = []
    for s in catalog.all():
        if qs_filter and not _qs_ok(s.qs_rank, qs_filter):
            continue
        best = collapse_school(profile, s, candidate_routes)
        if best is None:
            continue
        sc = _score_path(profile, best, s)
        results.append(Recommendation(
            school=s, path=best, score=sc,
            band_label=best.band))
    results.sort(key=lambda x: (-x.score, x.school.qs_rank or 9999))
    return results[:top_k]


def format_recommendation(rec: Recommendation) -> str:
    r = rec.path.requirement
    lines = [
        f"• {rec.school.name} (QS {rec.school.qs_rank} · {rec.school.country})",
        f"  线路[{ROUTE_LABEL.get(rec.path.path_type, rec.path.path_type)}] "
        f"难度={rec.band_label} 评分={rec.score}",
    ]
    notes = []
    if r.language_required and r.language_score:
        notes.append(f"{r.language_required}≥{r.language_score}")
    if r.exam and r.exam_score:
        notes.append(f"{r.exam}≥{r.exam_score}")
    if r.gpa_min:
        notes.append(f"GPA/均分≥{r.gpa_min}")
    if notes:
        lines.append("  " + " / ".join(notes))
    if rec.path.note:
        lines.append(f"  {rec.path.note}")
    return "\n".join(lines)
