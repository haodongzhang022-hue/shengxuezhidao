"""升学路径(线路)规则与推导。

核心概念: 一个学生能走哪几条"入学路径", 取决于其生源背景。

常见线路(route_key):
- gaokao              : 国内高考(部分海外院校接受高考成绩直申)
- ap                  : 中国大陆国际部/美高方向修读 AP
- alevel              : A-Level 课程体系(AQA/Edexcel/CIE)
- ib                  : IB 文凭体系
- overseas_highschool : 海外高中(美/英/加/澳 高中毕业文凭)
- country_local       : 目标国本地政策/本地高考(如美国本土、英国本土)
- transfer            : 转学
"""
ROUTE_RULES = {
    "gaokao": {
        "label": "国内高考",
        "for": ["CN"],                      # 适用国籍
        "needs": ["国内高中在读/毕业"],
        "note": "多数为中外合作或部分英澳名校接受高考成绩，需较高一本线；"
                "顶尖美国院校基本不接受。",
    },
    "ap": {
        "label": "AP 课程体系",
        "for": ["CN", "US", "HK", "SG"],
        "needs": ["美高/国际部课程", "AP 科目"],
        "note": "面向读 AP 的学生；美本为主，含英加澳多国。",
    },
    "alevel": {
        "label": "A-Level 体系",
        "for": ["CN", "GB", "HK", "SG", "MY"],
        "needs": ["A-Level 成绩", "通常 3-4 门 A/A*"],
        "note": "英联邦(英/港/澳/新)及部分欧美院校核心路径。",
    },
    "ib": {
        "label": "IB 文凭",
        "for": ["CN", "US", "GB", "CA", "AU"],
        "needs": ["IB DP 文凭"],
        "note": "全球接受度最高但课业强度大。",
    },
    "overseas_highschool": {
        "label": "海外高中",
        "for": ["US", "GB", "CA", "AU"],
        "needs": ["目标国高中毕业文凭"],
        "note": "以当地高中身份申请，享受本地申请池。",
    },
    "country_local": {
        "label": "目标国本地政策/高考",
        "for": ["US", "GB", "CA", "AU", "SG", "JP", "KR"],
        "needs": ["目标国公民/永居 或 当地高考"],
        "note": "仅适用于在该国本土读并参加当地升学体系的申请者。",
    },
}

# 中文标签
ROUTE_LABEL = {k: v["label"] for k, v in ROUTE_RULES.items()}


def country_local_routes(country_code: str) -> list:
    """某目标国是否有"本地政策"线路。"""
    rule = ROUTE_RULES.get("country_local", {})
    return ["country_local"] if country_code.upper() in rule["for"] else []


def student_route_candidates(profile) -> list:
    """根据学生国籍+教育路线，推导其可尝试的入学路径线路(优先顺序)。

    返回 List[str] route_keys。
    """
    routes: list = []
    nat = (profile.nationality or "").upper()
    edu = (profile.education_route or "").lower()

    # 依据教育路线直接给
    if edu == "gaokao":
        routes.append("gaokao")
    elif edu == "ap":
        routes.append("ap")
    elif edu == "alevel":
        routes.append("alevel")
    elif edu == "ib":
        routes.append("ib")
    elif edu == "overseas_highschool":
        routes.append("overseas_highschool")

    # 兜底推导: 海外地点无指定路线 -> 海外高中
    if not routes and profile.location:
        low = profile.location.lower()
        if not any(k in low for k in ("中国", "china", "内地", "北京", "上海", "广东",
                                      "江苏", "浙江", "山东")):
            routes.append("overseas_highschool")

    if not routes:
        # 默认: 中国大陆学生至少可尝试 AP / A-Level / IB / 高考
        if nat == "CN":
            routes = ["gaokao", "ap", "alevel", "ib"]

    # 去重保序
    seen = set()
    ordered = [r for r in routes if not (r in seen or seen.add(r))]

    # 若国籍为中国大陆走国际课程, gaokao 一般不可行 -> 若在 gaokao 列表中剔除(除非真在读高考)
    # (此处保守: 教育路线明确的就不再混入 gaokao)
    return ordered
