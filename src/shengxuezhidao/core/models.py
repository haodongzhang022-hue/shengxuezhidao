"""领域模型：学校、入学路径、路径要求、学生画像。

升学本体需要表达的核心事实:
- 同一所大学可以有 N 条入学路径(线路)并存
  (国内高考 / 大陆地区国际生 AP / A-Level / IB / 海外高中 / 各国本地政策)
- 每条路径拥有一组要求(语言、标化、GPA/分数、预算、难度分级)
- 学生画像 -> 通过"坍缩"收敛出该学生实际可行的路径子集
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------- 通用枚举
class QSPart(str):
    """QS 世界大学排名区间分段(便于检索)。"""

    TOP10 = "top10"
    TOP50 = "top50"
    TOP100 = "top100"
    TOP200 = "top200"
    TOP500 = "top500"


class ScoreBand(str):
    """难度/要求水平带(用于低门槛偏好的量化比较)。"""

    VERY_HARD = "very_hard"  # 极难(顶尖/极高录取门槛)
    HARD = "hard"            # 难
    MEDIUM = "medium"        # 中等
    REACHABLE = "reachable"  # 相对可达/低门槛
    ACCESSIBLE = "accessible"  # 最容易


BAND_RANK = {b: i for i, b in enumerate(
    [ScoreBand.VERY_HARD, ScoreBand.HARD, ScoreBand.MEDIUM,
     ScoreBand.REACHABLE, ScoreBand.ACCESSIBLE])}


# ---------------------------------------------------------------- 数据结构
@dataclass
class PathRequirement:
    """一条入学路径的量化要求。"""

    language_required: str = ""       # 语言类型要求, 如 IELTS / TOEFL
    language_score: float = 0.0       # 语言分数下限
    language_note: str = ""           # 语言备注(如小分要求)
    exam: str = ""                    # 需要参加的标化考试类型
    exam_score: float = 0.0           # 标化成绩下限
    exam_note: str = ""               # 标化备注(如 AP 门数 / AL 科目与等级)
    gpa_min: float = 0.0              # GPA/均分要求(百分制或 4.0)
    gpa_note: str = ""                # 均分备注
    annual_cost: float = 0.0          # 预估年成本(人民币, 学费+生活费, 0=未知)
    cost_currency: str = "CNY"
    note: str = ""                    # 其它补充(签证/面试/地区国籍限制等)


@dataclass
class AdmissionPath:
    """一所大学下的一种入学路径(线路)。"""

    path_type: str                    # route_key: gaokao / ap / alevel / ib /
                                      #           overseas_highschool / country_local ...
    path_name: str = ""               # 人类可读路径名
    applicable_countries: List[str] = field(default_factory=list)  # 适用国籍/生源
    requirement: PathRequirement = field(default_factory=PathRequirement)
    band: str = ScoreBand.MEDIUM      # 该路径对一般申请者的难度带
    eligibility: List[str] = field(default_factory=list)  # 资格/前置条件
    deadline: str = ""                # 申请截止(描述)
    note: str = ""

    @property
    def key(self) -> str:
        return self.path_type


@dataclass
class School:
    """一所世界高校及其多路径入学要求。"""

    name: str
    country: str
    region: str = ""
    qs_rank: int = 0                    # QS 综合排名
    qs_part: str = QSPart.TOP500
    fields: List[str] = field(default_factory=list)  # 强势学科标签
    city: str = ""
    tuition_currency: str = "CNY"
    paths: List[AdmissionPath] = field(default_factory=list)

    def path(self, path_type: str) -> Optional[AdmissionPath]:
        for p in self.paths:
            if p.path_type == path_type:
                return p
        return None

    def available_routes(self) -> List[str]:
        return [p.path_type for p in self.paths]

    @property
    def min_band(self) -> str:
        """该校所有路径中最"低门槛"的难度带(用于低门槛推荐排序)。"""
        if not self.paths:
            return ScoreBand.VERY_HARD
        return min((p.band for p in self.paths),
                   key=lambda b: BAND_RANK.get(b, 99))


@dataclass
class StudentProfile:
    """学生画像 - 用于对可行路径做"坍缩"。"""

    # 生源背景(决定可走哪些路径线路)
    nationality: str = "CN"            # 国籍, 如 CN / US / ...
    education_route: str = ""          # gaokao / ap / alevel / ib /
                                       # overseas_highschool / unknown
    location: str = ""                 # 现就读地(省内/国内/国外高中)
    grade12_year: int = 0              # 毕业年份

    # 学业表现(用于匹配要求)
    language_score: Optional[float] = None    # 已有语言分数(IELTS>=1 or TOEFL scale)
    language_type: str = "IELTS"
    gpa: Optional[float] = None               # 均分
    exam_score: Optional[float] = None        # 已有标化
    exam_type: str = ""
    courses: List[str] = field(default_factory=list)  # 已学/可选科目

    # 偏好(用于推荐与低门槛)
    pref_countries: List[str] = field(default_factory=list)  # 偏好的目标国家
    pref_majors: List[str] = field(default_factory=list)      # 偏好专业/学科
    pref_bands: List[str] = field(default_factory=list)       # 难度偏好(可选 low/mid/high)
    max_budget: Optional[float] = None    # 预算上限(人民币/年)
    want_low_threshold: bool = False      # 是否倾向相对低门槛方案

    def __post_init__(self):
        # 未指定生源路径但给了海外高中地点, 自动推导
        if not self.education_route and self.location:
            low = self.location.lower()
            if "中国" not in low and "china" not in low and "内地" not in low:
                self.education_route = "overseas_highschool"
