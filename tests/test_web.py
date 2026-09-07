"""HTTP 查询服务(轻量 REST)测试。"""
import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from shengxuezhidao.web import serve


@pytest.fixture()
def client():
    """启动一个临时 HTTP 服务并返回客户端函数。"""
    httpd = serve("127.0.0.1", 0)  # port=0 由系统分配空闲端口
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        with urllib.request.urlopen(base + path) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def post(path, data):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    yield {"get": get, "post": post}
    httpd.shutdown()


def _q(text):
    return urllib.parse.quote(text)


# ---------------------------------------------------------------- 基础端点
def test_health(client):
    data = client["get"]("/health")["data"]
    assert data["status"] == "ok"
    assert data["service"] == "shengxuezhidao"
    assert data["schools"] > 0


def test_stats(client):
    data = client["get"]("/stats")["data"]
    assert data["total_schools"] > 0
    assert "by_country" in data
    assert data["total_schools"] == sum(data["by_country"].values())


def test_routes(client):
    data = client["get"]("/routes")["data"]
    keys = {r["key"] for r in data}
    assert {"gaokao", "ap", "alevel", "ib"} <= keys


# ---------------------------------------------------------------- /search
def test_search_get_with_chinese(client):
    res = client["get"](f"/search?country={_q('英国')}&route=alevel")
    assert res["ok"] is True
    assert res["total"] > 0
    schools = [r["school"]["name"] for r in res["data"]]
    assert "University of Manchester" in schools


def test_search_post_body(client):
    res = client["post"]("/search", {"country": "澳大利亚", "route": "gaokao"})
    assert res["total"] > 0
    assert all(r["school"]["country"] == "澳大利亚" for r in res["data"])


def test_search_no_result_returns_empty(client):
    res = client["post"]("/search", {"country": "火星", "route": "alevel"})
    assert res["ok"] is True
    assert res["total"] == 0
    assert res["data"] == []


# ---------------------------------------------------------------- /recommend
def test_recommend_gaokao_low(client):
    res = client["post"]("/recommend", {
        "route": "gaokao", "ielts": 6.5, "budget": 400000,
        "low": True, "top": 5,
    })
    assert res["data"]["total"] > 0
    first = res["data"]["recommendations"][0]
    assert "school" in first
    # 低门槛偏好下曼彻斯特(accessible)应较靠前
    names = [r["school"]["name"] for r in res["data"]["recommendations"]]
    assert "University of Manchester" in names[:3]


def test_recommend_profile_fields(client):
    res = client["post"]("/recommend", {
        "education_route": "alevel", "language_type": "IELTS",
        "language_score": 7.0, "pref_countries": ["英国"],
    })
    prof = res["data"]["profile"]
    assert prof["education_route"] == "alevel"
    assert prof["language_score"] == 7.0


# ---------------------------------------------------------------- /ask
def test_ask_get(client):
    res = client["get"](f"/ask?q={_q('澳洲哪些学校接受高考成绩')}")
    assert res["ok"] is True
    assert res["data"]["answer"]
    assert res["data"]["source"] in ("local-retrieval", "llm")


def test_ask_post(client):
    res = client["post"]("/ask", {"question": "曼彻斯特大学高考要求", "country": "英国"})
    assert res["ok"] is True
    assert "曼彻斯特" in res["data"]["answer"]


def test_ask_missing_question_400(client):
    with pytest.raises(urllib.error.HTTPError) as ei:
        client["post"]("/ask", {})
    assert ei.value.code == 400


# ---------------------------------------------------------------- /llm-config
def test_llm_config(client):
    data = client["get"]("/llm-config")["data"]
    assert data["provider"]
    assert data["model"]


# ---------------------------------------------------------------- 404
def test_unknown_path_404(client):
    with pytest.raises(urllib.error.HTTPError) as ei:
        client["get"]("/unknown-endpoint")
    assert ei.value.code == 404
    body = json.loads(ei.value.read().decode("utf-8"))
    assert body["ok"] is False
    assert "error" in body
