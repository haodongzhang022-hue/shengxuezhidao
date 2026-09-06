"""数据源抽象与实现。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ...core.catalog import Catalog, _to_school
from ...core.models import School


class DataSource(ABC):
    """学校入学要求数据源。"""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> List[School]:
        """抓取/读取一批最新学校数据。"""


class JsonSource(DataSource):
    """从本地/下载的 JSON(含外部同步产物)读取学校列表。"""

    name = "json"

    def __init__(self, path: str):
        self.path = Path(path)

    def fetch(self) -> List[School]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("schools", [])
        return [_to_school(d) for d in items]


class OfficialManualSource(DataSource):
    """官方手动维护目录(推荐正式用)。

    结构:
        <dir>/*.json  每文件一个 JSON 列表, 与种子格式一致, 由运营据官网持续更新。
    """
    name = "official"

    def __init__(self, directory: str):
        self.directory = Path(directory)

    def fetch(self) -> List[School]:
        schools: List[School] = []
        for f in sorted(self.directory.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("schools", [])
            schools.extend(_to_school(d) for d in items)
        return schools
