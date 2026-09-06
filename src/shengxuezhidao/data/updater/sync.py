"""自动同步入口: 把源数据合并进 Catalog(幂等 upsert)。"""
from __future__ import annotations

from typing import Optional

from ...core.catalog import Catalog
from .source import DataSource


def sync_catalog(catalog: Catalog, source: DataSource,
                 dry_run: bool = False) -> dict:
    """从 source 拉取最新数据, 与 catalog 比对后合并。

    返回统计: {fetched, added, updated, unchanged}
    """
    schools = source.fetch()
    added = updated = unchanged = 0
    for s in schools:
        old = catalog.get(s.name)
        if old is None:
            added += 1
        elif old == s:
            unchanged += 1
        else:
            updated += 1
        if not dry_run:
            catalog.upsert(s)
    return {"fetched": len(schools), "added": added,
            "updated": updated, "unchanged": unchanged}
