"""自动更新(数据同步)测试。"""
import dataclasses
import json

from shengxuezhidao.core.catalog import Catalog
from shengxuezhidao.data.seed import load_seed, SEED_SCHOOLS
from shengxuezhidao.data.updater import JsonSource, sync_catalog


def _school_dict():
    """构造与内置 Manchester 结构一致的字典(通过 dataclass 转 dict)。"""
    man = next(s for s in SEED_SCHOOLS if s.name == "University of Manchester")
    return dataclasses.asdict(man)


def test_sync_idempotent(tmp_path):
    c = Catalog()
    load_seed(c)
    f = tmp_path / "src.json"
    payload = {"schools": [_school_dict()]}
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    src = JsonSource(str(f))

    # 数据完全一致 -> 无变化
    stat = sync_catalog(c, src, dry_run=True)
    assert stat["unchanged"] >= 1

    # 改动某路径的雅思要求后再同步 -> updated 且实际合并
    payload["schools"][0]["paths"][0]["requirement"]["language_score"] = 7.0
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    stat2 = sync_catalog(c, src)
    assert stat2["updated"] >= 1
    man = c.get("University of Manchester")
    assert man.path("alevel").requirement.language_score == 7.0
