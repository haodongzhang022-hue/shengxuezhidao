"""自动更新机制脚手架。

正式场景: 通过授权数据源/官网抓取定期刷新各校入学要求, 见 examples/。
此处提供:
- DataSource 抽象 + JsonSource(读取外部 JSON)
- sync() 把抓取结果合并进 Catalog(自动更新入口, 幂等)
"""
from .source import DataSource, JsonSource, OfficialManualSource
from .sync import sync_catalog

__all__ = ["DataSource", "JsonSource", "OfficialManualSource", "sync_catalog"]
