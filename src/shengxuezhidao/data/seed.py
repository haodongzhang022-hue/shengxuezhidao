"""内置种子学校数据(演示级, 供本体跑通)。

说明: 正式数据应由自动更新流程从官网/授权数据源持续同步。
本种子数据用于演示"多线路 + 坍缩 + 低门槛 + 检索 + 知识库问答"完整链路,
数值为简化示意, 需以官方最新口径校准。
"""
from __future__ import annotations

from ..core.models import AdmissionPath, PathRequirement, School

# 便捷构造
def _path(pt, name, band, req=None, countries=None, elig=None, note="",
          deadline=""):
    return AdmissionPath(
        path_type=pt,
        path_name=name,
        applicable_countries=countries or [],
        requirement=req or PathRequirement(),
        band=band,
        eligibility=elig or [],
        deadline=deadline,
        note=note,
    )


def _school(name, country, rank, fields, paths, region="", city=""):
    return School(name=name, country=country, region=region, city=city,
                  qs_rank=rank, fields=fields, paths=paths)


SEED_SCHOOLS = [
    # ---------------- 英国 ----------------
    _school("Imperial College London", "英国", 2, ["工程", "自然科学", "商科", "计算机"],
            [
                _path("alevel", "A-Level 直申", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=7.0,
                                      language_note="单项≥6.5", exam="A-Level",
                                      exam_score=0, exam_note="通常 A*A*A-AAA",
                                      gpa_min=0),
                      countries=["CN", "GB", "HK", "SG"],
                      elig=["A-Level 3-4门", "部分需入学笔试(如 MAT/ENGAA)"],
                      deadline="1月截止(UCAS)", note="英联邦顶尖理工院校, 竞争极高"),
                _path("ib", "IB 文凭", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=7.0,
                                      exam="IB", exam_score=38, exam_note="HL 需高分"),
                      countries=["CN", "GB", "HK", "SG"]),
                _path("ap", "AP 成绩申请(美国方向也可申请英国)", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=7.0,
                                      exam="AP", exam_score=0, exam_note="建议多门5分+SAT",
                                      gpa_min=3.8),
                      countries=["US", "CN"], note="英校用 AP+SAT 申请亦可行但偏难"),
            ],
            region="欧洲/英国", city="伦敦"),
    _school("University of Cambridge", "英国", 3, ["全学科", "数学", "工程", "法学", "医学"],
            [
                _path("alevel", "A-Level 直申", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=7.5,
                                      exam="A-Level", exam_note="A*AA-A*A*A, 部分需入学考",
                                      gpa_min=0),
                      countries=["CN", "GB", "HK", "SG"], deadline="UCAS 10月中"),
                _path("ib", "IB 文凭", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=7.5,
                                      exam="IB", exam_score=40),
                      countries=["CN", "GB", "HK", "SG"]),
            ], region="欧洲/英国", city="剑桥"),
    _school("University of Manchester", "英国", 32, ["商科", "计算机", "工程", "社科"],
            [
                _path("alevel", "A-Level 直申", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="AAA-ABB",
                                      gpa_min=0, annual_cost=350000),
                      countries=["CN", "GB", "HK", "SG"], deadline="UCAS 常规"),
                _path("ap", "AP+SAT", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="AP", exam_note="多门4-5分", gpa_min=3.4,
                                      annual_cost=350000),
                      countries=["US", "CN"]),
                _path("gaokao", "高考成绩直申", "accessible",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_min=0, exam_note="需参加高考且分数达一本线",
                                      gpa_note="通常省一本线以上", annual_cost=350000),
                      countries=["CN"], elig=["国内高考"], deadline="视年份滚动",
                      note="曼彻斯特接受高考成绩, 是国内普高生的相对低门槛方案"),
            ], region="欧洲/英国", city="曼彻斯特"),
    _school("University of Edinburgh", "英国", 27, ["人文", "医学", "社科", "计算机"],
            [
                _path("alevel", "A-Level", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="AAB-AAA"),
                      countries=["CN", "GB", "HK", "SG"]),
                _path("gaokao", "高考成绩直申(部分学院)", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_note="成绩优异", gpa_min=0),
                      countries=["CN"]),
            ], region="欧洲/英国", city="爱丁堡"),

    # ---------------- 美国 ----------------
    _school("Stanford University", "美国", 6, ["全学科", "工程", "商科", "CS"],
            [
                _path("ap", "美国方向(AP/普通高中)", "very_hard",
                      PathRequirement(language_required="TOEFL", language_score=100,
                                      exam="SAT", exam_score=1450, exam_note="推荐AP多门5分",
                                      gpa_min=3.9, annual_cost=600000),
                      countries=["US", "CN", "HK", "SG"], deadline="EA/ED/RD",
                      note="美国 Top 大学本科不看国内高考; 主要走 SAT/AP+文书+活动"),
                _path("overseas_highschool", "美国高中毕业申", "very_hard",
                      PathRequirement(language_required="TOEFL", language_score=100,
                                      exam="SAT", exam_score=1450, gpa_min=3.9,
                                      annual_cost=600000),
                      countries=["US"], note="以美高身份申请, 属本地池但门槛仍高"),
            ], region="北美/美国", city="加州"),
    _school("University of California, Berkeley", "美国", 12, ["CS", "工程", "商科", "社科"],
            [
                _path("ap", "美本常规申请", "hard",
                      PathRequirement(language_required="TOEFL", language_score=90,
                                      exam="SAT/ACT", exam_score=0, gpa_min=3.8,
                                      annual_cost=480000),
                      countries=["US", "CN", "HK", "SG"], deadline="11月底(UC)"),
                _path("overseas_highschool", "美高申请", "hard",
                      PathRequirement(language_required="TOEFL", language_score=90,
                                      gpa_min=3.8, annual_cost=480000),
                      countries=["US"]),
            ], region="北美/美国", city="加州"),
    _school("University of Michigan", "美国", 44, ["工程", "商科", "教育", "社科"],
            [
                _path("ap", "美本常规", "reachable",
                      PathRequirement(language_required="TOEFL", language_score=88,
                                      exam="SAT/ACT", gpa_min=3.6,
                                      annual_cost=450000),
                      countries=["US", "CN", "HK", "SG"]),
                _path("overseas_highschool", "美高申请", "reachable",
                      PathRequirement(language_required="TOEFL", language_score=88,
                                      gpa_min=3.6, annual_cost=450000),
                      countries=["US"]),
            ], region="北美/美国", city="密歇根"),
    _school("Arizona State University", "美国", 219, ["工程", "商科", "CS"],
            [
                _path("ap", "美本常规(相对低门槛)", "accessible",
                      PathRequirement(language_required="TOEFL", language_score=61,
                                      exam="SAT/ACT", gpa_min=3.0, annual_cost=320000),
                      countries=["US", "CN", "HK", "SG"], deadline="滚动录取",
                      note="录取率较高, 语言/标化要求相对宽松, 常被用作保底校(录取率较高/要求宽松)"),
                _path("overseas_highschool", "美高申请", "accessible",
                      PathRequirement(language_required="TOEFL", language_score=61,
                                      gpa_min=3.0, annual_cost=320000),
                      countries=["US"]),
            ], region="北美/美国", city="亚利桑那"),

    # ---------------- 澳大利亚 ----------------
    _school("University of Melbourne", "澳大利亚", 13, ["医学", "商科", "工程", "法学"],
            [
                _path("gaokao", "高考成绩直申", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_min=0, gpa_note="各省一本线附近",
                                      annual_cost=330000),
                      countries=["CN"], elig=["国内高考"], deadline="每年2/7月入学",
                      note="澳洲八大普遍接受高考成绩, 是国内普高相对好走的国际名校路径"),
                _path("alevel", "A-Level", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="BBB以上"),
                      countries=["GB", "HK", "SG", "CN"]),
            ], region="大洋洲/澳大利亚", city="墨尔本"),
    _school("University of Sydney", "澳大利亚", 18, ["医学", "法学", "商科", "工程"],
            [
                _path("gaokao", "高考成绩直申", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_note="各省一本线上", gpa_min=0,
                                      annual_cost=340000),
                      countries=["CN"], note="接受高考, 门槛适中"),
                _path("alevel", "A-Level", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="BBB"),
                      countries=["GB", "HK", "SG", "CN"]),
            ], region="大洋洲/澳大利亚", city="悉尼"),

    # ---------------- 加拿大 ----------------
    _school("University of Toronto", "加拿大", 25, ["全学科", "工程", "医学", "商科"],
            [
                _path("gaokao", "高考成绩+会考", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_min=0, gpa_note="需一本线附近",
                                      annual_cost=300000),
                      countries=["CN"], note="多伦多大学可凭高考+会考成绩申请"),
                _path("alevel", "A-Level", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="BBB-ABB"),
                      countries=["GB", "HK", "SG", "CN"]),
                _path("overseas_highschool", "加拿大高中", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      gpa_min=3.4, annual_cost=300000),
                      countries=["CA"]),
            ], region="北美/加拿大", city="多伦多"),
    _school("University of British Columbia", "加拿大", 38, ["林业", "海洋", "商科", "CS"],
            [
                _path("gaokao", "高考成绩直申", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_note="一本线", gpa_min=0,
                                      annual_cost=290000),
                      countries=["CN"]),
                _path("alevel", "A-Level", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="BBB"),
                      countries=["GB", "HK", "SG", "CN"]),
            ], region="北美/加拿大", city="温哥华"),

    # ---------------- 中国香港 ----------------
    _school("University of Hong Kong", "中国香港", 17, ["全学科", "医学", "法学", "商科"],
            [
                _path("gaokao", "内地高考", "hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_min=0, gpa_note="需省排名前列/顶尖线",
                                      annual_cost=220000),
                      countries=["CN"], elig=["内地高考生"], deadline="多元卓越计划",
                      note="港大经高考招生, 录取门槛极高(接近清北线)"),
                _path("alevel", "A-Level", "hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="A*AA-AAB"),
                      countries=["GB", "HK", "SG", "CN"]),
                _path("ap", "AP+SAT", "hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="SAT", exam_score=1350, gpa_min=3.6,
                                      annual_cost=220000),
                      countries=["US", "CN", "HK", "SG"]),
                _path("country_local", "香港本地 DSE", "medium",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="DSE", gpa_min=0),
                      countries=["HK"], elig=["香港 DSE 考生"]),
            ], region="亚洲/中国香港", city="香港"),
    _school("The Chinese University of Hong Kong", "中国香港", 36, ["全学科", "商科", "医学", "传媒"],
            [
                _path("gaokao", "内地高考", "hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="高考", gpa_note="顶尖/一本高分段", gpa_min=0,
                                      annual_cost=220000),
                      countries=["CN"]),
                _path("alevel", "A-Level", "reachable",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="AAA-AAB"),
                      countries=["GB", "HK", "SG", "CN"]),
            ], region="亚洲/中国香港", city="香港"),

    # ---------------- 新加坡 ----------------
    _school("National University of Singapore", "新加坡", 8, ["全学科", "工程", "CS", "商科"],
            [
                _path("alevel", "A-Level", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="A*A*A-AAA",
                                      annual_cost=250000),
                      countries=["GB", "SG", "HK", "CN"], note="新加坡国立录取竞争极高"),
                _path("ap", "AP/SAT", "very_hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="SAT", exam_score=1500, gpa_min=3.8),
                      countries=["US", "CN", "SG", "HK"]),
            ], region="亚洲/新加坡", city="新加坡"),
    _school("Nanyang Technological University", "新加坡", 26, ["工程", "CS", "商科", "艺术"],
            [
                _path("alevel", "A-Level", "hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="A-Level", exam_note="AAA-AAA"),
                      countries=["GB", "SG", "HK", "CN"]),
                _path("ap", "AP/SAT", "hard",
                      PathRequirement(language_required="IELTS", language_score=6.5,
                                      exam="SAT", exam_score=1450, gpa_min=3.7),
                      countries=["US", "CN", "SG", "HK"]),
            ], region="亚洲/新加坡", city="新加坡"),
]


def load_seed(catalog) -> int:
    """把种子学校载入 catalog, 返回条数。"""
    for s in SEED_SCHOOLS:
        catalog.add(s)
    return len(SEED_SCHOOLS)
