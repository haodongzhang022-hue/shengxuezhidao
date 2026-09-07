"""Web 服务层: 将本体的检索/坍缩推荐/知识库问答暴露为轻量 REST API。

用标准库 http.server 实现, 零第三方依赖, 便于任意前端/脚本便捷调用。
"""
from .server import make_handler, serve, VERSION

__all__ = ["make_handler", "serve", "VERSION"]
