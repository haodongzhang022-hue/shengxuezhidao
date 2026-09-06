"""领域模型与 catalog 基础测试。"""
import pytest

from shengxuezhidao.core.catalog import Catalog
from shengxuezhidao.data.seed import load_seed, SEED_SCHOOLS


def test_seed_loads():
    c = Catalog()
    n = load_seed(c)
    assert n == len(SEED_SCHOOLS) > 0
    assert c.size == len(SEED_SCHOOLS)


def test_multipath_school():
    c = Catalog()
    load_seed(c)
    man = c.get("University of Manchester")
    assert man is not None
    # 曼大同时具备高考/AP/A-Level 三条线路
    routes = man.available_routes()
    assert "gaokao" in routes
    assert "alevel" in routes
    assert "ap" in routes


def test_rank_index():
    c = Catalog()
    load_seed(c)
    top50 = c.by_qs_part("top50")
    assert all(1 <= s.qs_rank <= 50 for s in top50)
    assert len(top50) > 0


def test_catalog_json_roundtrip(tmp_path):
    c = Catalog()
    load_seed(c)
    out = tmp_path / "out.json"
    assert c.save_json(str(out)) == c.size
    c2 = Catalog()
    assert c2.load_json(str(out)) == c.size
    assert c2.size == c.size
