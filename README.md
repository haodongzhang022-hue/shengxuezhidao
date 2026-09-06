# 升学之道 · 全球 Top500 大学升学智能查询系统（本体）

面向 **世界大学排名(QS)前 500 高校** 的升学智能查询系统本体。

> 一句话：**收录 → 检索 → 多线路建模 → 学生画像坍缩 → 低门槛推荐 → AI 知识库二次询问**。

## 一、它解决什么问题

同一个学生可以走 **不同的升学线路** 去申请同一所大学，例如：
国内高考、AP、A-Level、IB、海外高中、目标国本地政策等。

- 一所大学在不同线路下的**入学要求**往往不同；
- 学生背景不同，**能走哪条线路**也不一样；
- 系统要能根据学生具体情况 **“坍缩”** 出可行且**相对低门槛**的申请方案，
  并支持 **带知识库效果的对话式二次询问**。

## 二、核心能力

| 模块 | 说明 |
|------|------|
| 数据收录层 `core` | 领域模型：学校 `School`、入学路径 `AdmissionPath`、路径要求 `PathRequirement`、学生画像 `StudentProfile`；资料库 `Catalog`（加载/保存/多路径索引） |
| 检索引擎 `engine` | 多维检索（国家/QS分段/专业/线路/预算/关键词）+ **坍缩匹配** + **低门槛/难度偏好推荐** |
| 规则层 `rules` | 各线路适用规则（高考/AP/A-Level/IB/海外高中/目标国本地）与学生可走线路推导 |
| AI 知识库 `ai` | 把学校数据转成可检索文本片段；支持检索增强(RAG)、自然语言问答、画像补全型二次询问；可选接 OpenAI 兼容大模型做生成式回答 |
| 自动更新 `data.updater` | 数据源抽象 + 幂等同步（官网/授权 JSON 增量合并） |
| 命令行 `cli` | 交互入口：`search / recommend / ask / update / export / stats / routes` |

## 三、快速开始

```bash
pip install -e .

# 资料库概览
python -m shengxuezhidao stats

# 可选升学线路说明
python -m shengxuezhidao routes

# 多维检索：英国接受 A-Level 的学校
python -m shengxuezhidao search --country 英国 --route alevel

# 学生画像坍缩推荐：国内高考生、预算 40 万、倾向低门槛
python -m shengxuezhidao recommend --route gaokao --ielts 6.5 --budget 400000 --low

# AI 知识库问答（自然语言）
python -m shengxuezhidao ask "澳洲哪些学校接受高考成绩"
python -m shengxuezhidao ask "曼彻斯特大学高考要多少分，需要雅思吗"

# 进入交互式连续问答（模拟二次询问）
python -m shengxuezhidao ask

# 导出资料库 JSON（供归档/增量同步）
python -m shengxuezhidao export data/schools.json

# 自动更新：从外部 JSON 数据源同步并导出
python -m shengxuezhidao update data/schools.json --export data/schools.json
```

### 推荐示例（坍缩）

```
python -m shengxuezhidao recommend --route gaokao --ielts 6.5 --budget 400000 --low --top 8
```

> 会输出该高考生**可走高考线路**的学校，按可行性排序；
> 相对低门槛的曼彻斯特/澳洲/加拿大靠前，难度极高的港大靠后——这就是“低门槛偏好坍缩”。

## 四、接入大模型（可选，做生成式问答）

不接模型时，系统内置**检索即答**（离线可跑通演示）；
如需 LLM 生成式回答，设置以下环境变量即可（OpenAI 兼容接口）：

```bash
export SXZD_LLM_API_KEY=sk-xxx
export SXZD_LLM_BASE_URL=https://api.example.com/v1
export SXZD_LLM_MODEL=deepseek-v4-flash   # 或其它 OpenAI 兼容模型
```

## 五、数据与自动更新

- **种子数据**：`src/shengxuezhidao/data/seed.py` 内置演示级数据（含多线路），
  数值为示意，**正式口径需以官网/授权数据源校准**。
- **数据格式**：`School` JSON 支持多 `paths`，路径含 `requirement`，见 `tests` 与导出样例。
- **自动更新链路**：
  1. 运营/定时任务抓取官网最新要求 → 落地为 JSON（与种子格式一致）；
  2. `python -m shengxuezhidao update <dir_or_file> --export out.json`
     → 幂等合并进资料库并导出；
  3. 支持 `--dry-run` 先比对再落地。
  - 建议用独立 `data_source/` 目录维护官方数据，正式生产可接定时调度。

## 六、测试

```bash
pip install -e ".[dev]"
python -m pytest -q
```

## 七、项目结构

```
src/shengxuezhidao/
  core/    # 领域模型 + 资料库 Catalog
  engine/  # 检索 + 坍缩匹配 + 低门槛推荐 + 线路规则
  ai/      # 知识库 KB + AI 助手(问答/追问)
  data/    # 种子数据 + 自动更新 updater
  cli/     # 命令行入口
data/      # 导出的资料库 JSON（演示）
tests/     # pytest 测试
```
