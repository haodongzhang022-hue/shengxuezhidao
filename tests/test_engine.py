"""检索与坍缩推荐测试。"""
from shengxuezhidao.core.catalog import Catalog
from shengxuezhidao.core.models import StudentProfile
from shengxuezhidao.data.seed import load_seed
from shengxuezhidao.engine.matcher import SearchQuery, collapse, search


def _cat():
    c = Catalog()
    load_seed(c)
    return c


def test_search_country_route():
    c = _cat()
    res = search(c, SearchQuery(country="英国", route="alevel"))
    assert len(res) >= 3
    assert all(r.school.country == "英国" for r in res)
    assert all(any(p.path_type == "alevel" for p in r.matched_paths) for r in res)


def test_search_rank_field():
    c = _cat()
    res = search(c, SearchQuery(qs_part="top10", field="工程"))
    assert res
    for r in res:
        assert r.school.qs_rank <= 10


def test_collapse_gaokao_prefers_reachable():
    c = _cat()
    prof = StudentProfile(nationality="CN", education_route="gaokao",
                          location="中国", language_score=6.5,
                          want_low_threshold=True)
    recs = collapse(prof, c, top_k=20)
    assert recs
    # 坍缩结果只应包含确实可走 gaokao 且满足基本条件的学校
    names = [r.school.name for r in recs]
    assert "University of Manchester" in names
    assert "University of Melbourne" in names
    # 美国方向(不接受高考的)不应出现在 gaokao 坍缩结果
    assert "Stanford University" not in names


def test_collapse_alevel():
    c = _cat()
    prof = StudentProfile(nationality="CN", education_route="alevel",
                          language_score=6.5)
    recs = collapse(prof, c, top_k=5)
    assert recs
    for r in recs:
        assert r.path.path_type == "alevel"


def test_low_threshold_ranking():
    c = _cat()
    prof_hi = StudentProfile(nationality="CN", education_route="gaokao",
                             language_score=7.5, want_low_threshold=True)
    recs = collapse(prof_hi, c, top_k=20)
    # 低门槛偏好下, 相对可达(Australia/Manchester)应排在 HK(very hard)之前
    idx_man = next(i for i, r in enumerate(recs)
                   if r.school.name == "University of Manchester")
    idx_hku = next(i for i, r in enumerate(recs)
                   if r.school.name == "University of Hong Kong")
    assert idx_man < idx_hku
