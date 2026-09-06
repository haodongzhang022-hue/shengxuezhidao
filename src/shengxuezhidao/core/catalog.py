"""学校资料库: 加载/保存/索引/自动更新脚手架。

Catalog 是"本体"的数据中枢:
- 从内置种子数据或外部 JSON 目录加载学校
- 维护多维索引便于快速检索(国家/排名段/学科)
- 提供 merge(upsert) 与 apply_updates 支撑"自动更新"
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import AdmissionPath, PathRequirement, School


def _to_school(d: dict) -> School:
    paths = []
    for pd_ in d.get("paths", []):
        req = PathRequirement(**(pd_.get("requirement", {}) or {}))
        paths.append(AdmissionPath(
            path_type=pd_["path_type"],
            path_name=pd_.get("path_name", ""),
            applicable_countries=pd_.get("applicable_countries", []),
            requirement=req,
            band=pd_.get("band", "medium"),
            eligibility=pd_.get("eligibility", []),
            deadline=pd_.get("deadline", ""),
            note=pd_.get("note", ""),
        ))
    return School(
        name=d["name"],
        country=d.get("country", ""),
        region=d.get("region", ""),
        qs_rank=int(d.get("qs_rank", 0)),
        qs_part=d.get("qs_part", "top500"),
        fields=list(d.get("fields", [])),
        city=d.get("city", ""),
        tuition_currency=d.get("tuition_currency", "CNY"),
        paths=paths,
    )


def _to_dict(s: School) -> dict:
    return {
        "name": s.name,
        "country": s.country,
        "region": s.region,
        "qs_rank": s.qs_rank,
        "qs_part": s.qs_part,
        "fields": s.fields,
        "city": s.city,
        "tuition_currency": s.tuition_currency,
        "paths": [
            {
                "path_type": p.path_type,
                "path_name": p.path_name,
                "applicable_countries": p.applicable_countries,
                "band": p.band,
                "eligibility": p.eligibility,
                "deadline": p.deadline,
                "note": p.note,
                "requirement": dataclass_to_dict(p.requirement),
            }
            for p in s.paths
        ],
    }


def dataclass_to_dict(obj) -> dict:
    import dataclasses
    return dataclasses.asdict(obj)


class Catalog:
    """学校资料库本体。"""

    def __init__(self):
        self._schools: Dict[str, School] = {}  # key: name

    # ------------------------------------------------------------ 添加/删除
    def add(self, school: School) -> None:
        self._schools[school.name] = school

    def upsert(self, school: School) -> bool:
        """新增或整体替换同一学校。返回是否为新增。"""
        existed = school.name in self._schools
        self._schools[school.name] = school
        return not existed

    def remove(self, name: str) -> bool:
        return self._schools.pop(name, None) is not None

    def get(self, name: str) -> Optional[School]:
        return self._schools.get(name)

    def all(self) -> List[School]:
        return sorted(self._schools.values(), key=lambda s: s.qs_rank or 9999)

    @property
    def size(self) -> int:
        return len(self._schools)

    # ------------------------------------------------------------ 加载/保存
    def load_json(self, path: str | os.PathLike) -> int:
        """从一个 JSON 文件/目录加载学校数据, 返回加载条数。"""
        p = Path(path)
        count = 0
        if p.is_dir():
            for f in sorted(p.glob("*.json")):
                count += self._load_one(f)
        elif p.is_file():
            count = self._load_one(p)
        return count

    def _load_one(self, path: Path) -> int:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("schools", [])
        n = 0
        for d in items:
            self.add(_to_school(d))
            n += 1
        return n

    def save_json(self, path: str | os.PathLike) -> int:
        """将当前资料库序列化为单个 JSON 文件。返回条数。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schools": [_to_dict(s) for s in self.all()]}
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return len(self._schools)

    # ------------------------------------------------------------ 更新/合并
    def apply_updates(self, updates: Iterable[School]) -> int:
        """把外部抓取到的最新学校数据合并进库(自动更新入口)。"""
        changed = 0
        for school in updates:
            old = self.get(school.name)
            if old and old == school:
                continue
            self.add(school)
            changed += 1
        return changed

    # ------------------------------------------------------------ 索引
    def by_country(self, country: str) -> List[School]:
        return [s for s in self.all() if s.country.lower() == country.lower()]

    def by_qs_part(self, part: str) -> List[School]:
        if part == "top10":
            return [s for s in self.all() if 1 <= s.qs_rank <= 10]
        if part == "top50":
            return [s for s in self.all() if 1 <= s.qs_rank <= 50]
        if part == "top100":
            return [s for s in self.all() if 1 <= s.qs_rank <= 100]
        if part == "top200":
            return [s for s in self.all() if 1 <= s.qs_rank <= 200]
        if part == "top500":
            return [s for s in self.all() if 1 <= s.qs_rank <= 500]
        return self.all()

    def has_route(self, route: str) -> List[School]:
        """支持某条路径线路的学校(如 gaokao / ap / alevel)。"""
        return [s for s in self.all() if s.path(route) is not None]
