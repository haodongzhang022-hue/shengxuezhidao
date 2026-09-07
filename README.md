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
| AI 知识库 `ai` | 把学校数据转成可检索文本片段；支持检索增强(RAG)、自然语言问答、画像补全型二次询问；**默认接 DeepSeek**，可切换任意 OpenAI 兼容大模型 |
| 自动更新 `data.updater` | 数据源抽象 + 幂等同步（官网/授权 JSON 增量合并） |
| 命令行 `cli` | 交互入口：`search / recommend / ask / llm-config / update / export / stats / routes / serve` |
| Web 查询服务 `web` | 零依赖轻量 HTTP API：把检索/坍缩推荐/知识库问答/统计暴露为 REST 接口，供前端与脚本便捷调用 |

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

# AI 知识库问答（自然语言，无 Key 走内置检索，有 Key 走 DeepSeek）
python -m shengxuezhidao ask "澳洲哪些学校接受高考成绩"
python -m shengxuezhidao ask "曼彻斯特大学高考要多少分，需要雅思吗"

# 查看 LLM 接入配置 / 生成环境变量示例
python -m shengxuezhidao llm-config
python -m shengxuezhidao llm-config --env

# 进入交互式连续问答（模拟二次询问）
python -m shengxuezhidao ask

# 导出资料库 JSON（供归档/增量同步）
python -m shengxuezhidao export data/schools.json

# 自动更新：从外部 JSON 数据源同步并导出
python -m shengxuezhidao update data/schools.json --export data/schools.json

# 启动轻量 HTTP 查询服务（便捷查询，供任意前端/脚本调用）
python -m shengxuezhidao serve --host 127.0.0.1 --port 8000
```

### 推荐示例（坍缩）

```
python -m shengxuezhidao recommend --route gaokao --ielts 6.5 --budget 400000 --low --top 8
```

> 会输出该高考生**可走高考线路**的学校，按可行性排序；
> 相对低门槛的曼彻斯特/澳洲/加拿大靠前，难度极高的港大靠后——这就是“低门槛偏好坍缩”。

## 四、AI 接入配置

### 4.1 默认接入 DeepSeek

本系统 **默认指向 DeepSeek 官方 API**（OpenAI 兼容接口），开箱即用：

```bash
# 只需设置 API Key 即可启用 DeepSeek
export SXZD_LLM_API_KEY=sk-你的DeepSeek密钥

# 无需设置 base_url / model, 默认已是:
#   base_url = https://api.deepseek.com
#   model    = deepseek-v4-flash
```

查看当前配置状态:

```bash
python -m shengxuezhidao llm-config
```

### 4.2 三种自定义接入方式（确保通用性）

系统支持通过 **环境变量 / JSON 配置文件 / CLI 参数** 三种方式自由切换为
任意 OpenAI 兼容大模型服务商。

#### 方式一：环境变量（最常用）

```bash
# 全部可配置项
export SXZD_LLM_API_KEY=sk-xxx            # API 密钥（必填）
export SXZD_LLM_BASE_URL=https://...      # API 地址（默认 DeepSeek）
export SXZD_LLM_MODEL=model-name          # 模型名
export SXZD_LLM_PROVIDER=deepseek         # 提供商名（见内置预设表）
export SXZD_LLM_TIMEOUT=60                # 超时秒数
export SXZD_LLM_MAX_TOKENS=2048           # 生成上限
export SXZD_LLM_TEMPERATURE=0.2           # 温度
```

#### 方式二：JSON 配置文件

```bash
# 复制模板
cp examples/llm_config.example.json sxzd_llm.json
# 编辑填入 API Key, 然后:
export SXZD_LLM_CONFIG=./sxzd_llm.json

# 单值环境变量优先于配置文件
```

#### 方式三：CLI 参数（临时覆盖）

```bash
python -m shengxuezhidao ask "澳洲哪些大学接受高考" \
  --api-key sk-xxx \
  --base-url https://api.deepseek.com \
  --model deepseek-v4-flash \
  --provider deepseek
```

### 4.3 内置 provider 预设

| provider | base_url | model |
|----------|----------|-------|
| `deepseek` (默认) | `https://api.deepseek.com` | `deepseek-v4-flash` |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| `glm` | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| `ollama` | `http://localhost:11434/v1` | `llama3` |
| `moonshot` | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| `siliconflow` | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |

使用预设切换模型只需：

```bash
# 接 OpenAI
export SXZD_LLM_PROVIDER=openai
export SXZD_LLM_API_KEY=sk-openai-key

# 接 GLM
export SXZD_LLM_PROVIDER=glm
export SXZD_LLM_API_KEY=sk-glm-key

# 接本地 Ollama
export SXZD_LLM_PROVIDER=ollama
```

### 4.4 配置优先级

```
CLI 参数  >  环境变量  >  JSON 配置文件  >  内置默认(DeepSeek)
```

### 4.5 未配置 Key 时的行为

没有设置 `SXZD_LLM_API_KEY` 时，系统自动使用**本地检索回答**（离线可跑通）。
此时在 `ask` 命令启动时会给出提示，配置 Key 后自动切换为 LLM 生成式回答。

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

## 六、Web 查询服务（HTTP API）

本体提供零依赖的轻量 REST 服务，把检索/坍缩推荐/知识库问答/统计暴露成接口，
便于任何前端、脚本做“便捷查询”。

### 启动服务

```bash
python -m shengxuezhidao serve --host 127.0.0.1 --port 8000
```

> 仅用 Python 标准库实现，无需安装 Flask。加 `Ctrl+C` 即可停止。

### 端点一览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（含资料库学校数） |
| `/stats` | GET | 资料库统计（按国家/排名段/线路分布） |
| `/routes` | GET | 可选升学路径线路说明 |
| `/search` | GET/POST | 多维检索（国家/QS分段/专业/线路/关键词/预算） |
| `/recommend` | POST | 学生画像坍缩推荐（低门槛/难度偏好） |
| `/ask` | GET/POST | 知识库问答 / 二次询问（可接 LLM） |
| `/llm-config` | GET | 查看当前 LLM 接入配置 |

所有接口均返回 `{"ok": bool, "data": ...}`，utf-8 JSON；已带 CORS 头，浏览器可跨域直连。

### 使用示例

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 检索：英国接受 A-Level 的学校
curl "http://127.0.0.1:8000/search?country=英国&route=alevel"

# 坍缩推荐：国内高考生、IELTS 6.5、预算 40 万、倾向低门槛
curl -X POST http://127.0.0.1:8000/recommend -H 'Content-Type: application/json' \
  -d '{"route":"gaokao","ielts":6.5,"budget":400000,"low":true,"top":5}'

# 知识库问答
curl "http://127.0.0.1:8000/ask?q=澳洲哪些学校接受高考成绩"
curl -X POST http://127.0.0.1:8000/ask -H 'Content-Type: application/json' \
  -d '{"question":"曼彻斯特大学高考要多少分？","country":"英国"}'
```

> 建议 GET 的中文参数做一次 URL 编码；`POST /recommend` 支持
> `nationality / route / ielts / gpa / budget / countries / majors / low / top`
> 等画像字段，未坍缩出方案时会附带 `clarify` 追问清单。

## 七、测试

```bash
pip install -e ".[dev]"
python -m pytest -q
```

## 八、项目结构

```
src/shengxuezhidao/
  core/    # 领域模型 + 资料库 Catalog
  engine/  # 检索 + 坍缩匹配 + 低门槛推荐 + 线路规则
  ai/      # 知识库 KB + LLM 配置(config.py) + AI 助手(assistant.py)
  data/    # 种子数据 + 自动更新 updater
  cli/     # 命令行入口
  web/     # 轻量 HTTP 查询服务(server.py, 零依赖 REST API)
examples/  # LLM 配置模板等示例文件
data/      # 导出的资料库 JSON（演示）
tests/     # pytest 测试
```
