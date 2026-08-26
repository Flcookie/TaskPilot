# TaskPilot

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/Flcookie/TaskPilot/actions/workflows/lint.yaml/badge.svg)](https://github.com/Flcookie/TaskPilot/actions)

[English](./README.md) | [简体中文](./README_zh.md)

**TaskPilot** 是面向复杂任务执行的轻量 Agent Runtime。

每一次请求都是一个显式 **Task**：创建、运行、中断、恢复、取消、回放、评测。事件写入日志并通过 SSE 推送。Skill、工具、记忆和中间件围绕执行引擎工作，而不是写死在一张调研图里。

内置的 Plan-Execute / DeepResearch 图是 Runtime 上的一种 **Workflow**。报告、播客、PPT 是工作流产物，不是产品本身。

参考 Plan-Execute / DeepResearch 工作流实现，在此基础上重新抽象 Task Runtime，将研究图下沉为 Workflow，通过 Task/Event、Middleware、Tool Registry、Skill、Long-term Memory、Observability、Evaluation 和进程隔离构建通用复杂任务执行框架。

## 目录

- [架构](#架构)
- [Runtime](#runtime)
- [特性](#特性)
- [开始使用](#开始使用)
- [搜索、爬取与知识库](#搜索爬取与知识库)
- [文本转语音](#文本转语音)
- [Docker](#docker)
- [开发](#开发)
- [常见问题](#常见问题)
- [许可证](#许可证)
- [致谢](#致谢)

## 架构

```
客户端（Web UI / CLI）
        │
        ▼
FastAPI
  /api/tasks*           显式任务生命周期
  /api/chat/stream      兼容流式入口
        │
        ▼
TaskPilot Runtime
  TaskService · EventStore · Middleware · ToolRegistry
  Skill（按需加载） · Memory · Evaluation · 进程隔离
        │
        ▼
LangGraph Workflows
  DeepResearch · podcast · presentation · …
        │
        ▼
TaskEvent 日志  →  SSE 实时 / 回放（?task=） / 评测
```

Runtime 负责任务生命周期、可观测性和策略；LangGraph 负责图执行。`/api/chat/stream` 仍可作为兼容入口；新接入请走 `/api/tasks`。

## Runtime

### 任务生命周期

状态：`pending` → `running` → `interrupted` | `succeeded` | `failed` | `cancelled`。

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` | `/api/tasks` | 创建任务（默认工作流：`deep_research`） |
| `GET` | `/api/tasks/{id}` | 状态与元数据 |
| `GET` | `/api/tasks/{id}/events` | 事件日志（`after_seq` 分页） |
| `GET` | `/api/tasks/{id}/stream` | 启动或续传 SSE（`Last-Event-ID` 续流） |
| `POST` | `/api/tasks/{id}/cancel` | 取消运行中或待执行任务 |
| `POST` | `/api/tasks/{id}/resume` | 中断 / 失败后恢复 |
| `POST` | `/api/tasks/{id}/replay` | 将已存事件回放为 SSE |
| `POST` | `/api/tasks/{id}/evaluate` | 过程 + 报告 + Skill 加载对照 |

Web 回放：打开 `http://localhost:3000/chat?task=<task_id>`。

任务与事件默认写入 SQLite（`TASK_STORE_URL=sqlite:///data/tasks.sqlite`）。测试使用 `memory://`。

### 中间件

Hook 是订阅点（`before_task`、`before_tool`、`after_llm`、`on_error` 等）。默认栈：

`audit → skill → context_inject → token_accounting → tool_guard → memory_write`

Memory 是存储，不是中间件。`context_inject` 把检索到的记忆写入 prompt；`memory_write` 异步落盘新事实。

### Skill

Skill 是可复用的执行策略：描述、标签，以及 `allowed_tools`（该次运行的**可见**工具集）。Skill 按需加载；v1 不做 Skill 组合。

| Skill | 适用场景 |
|---|---|
| `deep_research` | 多信源调研与报告 |
| `data_analysis` | 数值、对比、偏 Python 的任务 |
| `report_writing` | 在已有材料上结构化成文 |

### Memory

三层：**preference**（偏好）、**background**（任务背景）、**fact**（事实）。默认存储：`MEMORY_STORE_URL=sqlite:///data/memory.sqlite`。

### 评测与隔离

- **过程指标**：计划质量、工具选择、失败恢复
- **报告指标**：原有报告质量评估
- **Skill 加载对照**：按需加载 vs 全量加载的 token / 延迟
- **Python 隔离**：代码在子进程中执行。这是进程隔离，不是安全沙箱。

## 特性

### Runtime

- 显式 Task：事件日志、SSE 续流与回放
- 基于 Hook 的中间件（审计、Skill 策略、Token 统计、工具兜底）
- 统一 `ToolRegistry` + `ToolResult`，覆盖内置工具与 MCP
- Skill 按需加载，按 Skill 限制 `allowed_tools`
- 长期记忆（偏好 / 背景 / 事实）
- Agent 评测（过程 + 报告 + Skill 加载）
- 通过 [litellm](https://docs.litellm.ai/docs/providers) 接入多数模型，含 OpenAI 兼容接口与 Qwen 等开源模型，详见 [配置指南](docs/configuration_guide.md)

### 工具和 MCP

- 🔍 **搜索和检索** — Tavily、InfoQuest、Brave Search，Jina / InfoQuest 爬取，私有知识库
- 📃 **RAG** — [Qdrant](https://qdrant.tech/)、[Milvus](https://milvus.io/)、[RAGFlow](https://github.com/infiniflow/ragflow)、VikingDB、MOI、Dify；输入框可 @ 知识库文件
- 🔗 **MCP** — 扩展私有 API、知识图谱、浏览等能力

### 人机协作

- 💬 **智能澄清** — 模糊任务规划前多轮确认（[指南](./docs/configuration_guide.md#multi-turn-clarification-feature)）
- 🧠 **人在环中** — 用自然语言接受或修改计划，也可自动接受
- 📝 **报告后期编辑** — 类 Notion 块编辑，支持 AI 润色 / 缩短 / 扩展（[tiptap](https://tiptap.dev/)）

### 工作流产物

- 🎙️ **播客和演示文稿** — 同一任务可生成脚本 + TTS 音频，以及简单 PPT

## 开始使用

TaskPilot 使用 Python 开发，并配有用 Node.js 编写的 Web UI。为确保顺利的设置过程，我们推荐使用以下工具：

### 推荐工具

- **[`uv`](https://docs.astral.sh/uv/getting-started/installation/):**
  简化 Python 环境和依赖管理。`uv`会自动在根目录创建虚拟环境并为您安装所有必需的包—无需手动安装 Python 环境。

- **[`nvm`](https://github.com/nvm-sh/nvm):**
  轻松管理多个 Node.js 运行时版本。

- **[`pnpm`](https://pnpm.io/installation):**
  安装和管理 Node.js 项目的依赖。

### 环境要求

确保您的系统满足以下最低要求：

- **[Python](https://www.python.org/downloads/):** 版本 `3.12+`
- **[Node.js](https://nodejs.org/en/download/):** 版本 `22+`

### 安装

```bash
# 克隆仓库
git clone https://github.com/Flcookie/TaskPilot.git
cd TaskPilot

# 安装依赖，uv将负责Python解释器和虚拟环境的创建，并安装所需的包
uv sync

# 使用您的API密钥配置.env
# Tavily: https://app.tavily.com/home
# Brave_SEARCH: https://brave.com/search/api/
# TTS: 如果您有TTS凭证，请添加
cp .env.example .env

# 查看下方的"支持的搜索引擎"和"文本转语音集成"部分了解所有可用选项

# 为您的LLM模型和API密钥配置conf.yaml
# 请参阅'docs/configuration_guide.md'获取更多详情
cp conf.yaml.example conf.yaml

# 安装marp用于PPT生成
# https://github.com/marp-team/marp-cli?tab=readme-ov-file#use-package-manager
brew install marp-cli
```

可选，通过[pnpm](https://pnpm.io/installation)安装 Web UI 依赖：

```bash
cd web
pnpm install
```

### 配置

请参阅[配置指南](docs/configuration_guide.md)获取更多详情。

> [! 注意]
> 在启动项目之前，请仔细阅读指南，并更新配置以匹配您的特定设置和要求。

任务与记忆默认写入 SQLite，重启后仍可回放任务、读取长期记忆。可在 `.env` 中覆盖：

```bash
TASK_STORE_URL=sqlite:///data/tasks.sqlite
MEMORY_STORE_URL=sqlite:///data/memory.sqlite
# TASK_STORE_URL=memory://
# MEMORY_STORE_URL=memory://
```

### 控制台 UI

运行项目的最快方法是使用控制台 UI。

```bash
# 在类bash的shell中运行项目
uv run main.py
```

### Web UI

本项目还包括一个 Web UI，提供更加动态和引人入胜的交互体验。
> [! 注意]
> 您需要先安装 Web UI 的依赖。

```bash
# 在开发模式下同时运行后端和前端服务器
# 在macOS/Linux上
./bootstrap.sh -d

# 在Windows上
bootstrap.bat -d
```
> [! 注意]
> 出于安全考虑，后端服务器默认绑定到 127.0.0.1 (localhost)。如果您需要允许外部连接（例如，在Linux服务器上部署时），您可以修改启动脚本中的主机地址为 0.0.0.0。（uv run server.py --host 0.0.0.0）
> 请注意，在将服务暴露给外部网络之前，请务必确保您的环境已经过适当的安全加固。

打开浏览器并访问[`http://localhost:3000`](http://localhost:3000)探索 Web UI。

回放已完成的任务：`http://localhost:3000/chat?task=<task_id>`。

在[`web`](./web/)目录中探索更多详情。

### Task API

后端启动后（`http://localhost:8000`）：

```bash
# 创建任务（默认工作流为 DeepResearch）
curl -s -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"什么是 MCP？"}],"auto_accepted_plan":true}'

# 流式执行（替换 TASK_ID）
curl -N http://localhost:8000/api/tasks/TASK_ID/stream
```

取消 / 恢复 / 回放 / 评测见 [Runtime](#runtime)。

## 搜索、爬取与知识库

### 公域搜索引擎

TaskPilot 支持多种搜索引擎，可以在`.env`文件中通过`SEARCH_API`变量进行配置：

- **Tavily**（默认）：专为 AI 应用设计的专业搜索 API
  - 需要在`.env`文件中设置`TAVILY_API_KEY`
  - 注册地址：<https://app.tavily.com/home>

- **InfoQuest**：可选的搜索与爬取服务
  - 需要在`.env`文件中设置`INFOQUEST_API_KEY`
  - 支持时间范围过滤和站点过滤

- **DuckDuckGo**：注重隐私的搜索引擎
  - 无需 API 密钥

- **Brave Search**：具有高级功能的注重隐私的搜索引擎
  - 需要在`.env`文件中设置`BRAVE_SEARCH_API_KEY`
  - 注册地址：<https://brave.com/search/api/>

- **Arxiv**：用于学术研究的科学论文搜索
  - 无需 API 密钥
  - 专为科学和学术论文设计

- **Searx/SearxNG**：自托管的元搜索引擎
  - 需要在`.env`文件中设置`SEARX_HOST`
  - 支持对接Searx或SearxNG

要配置您首选的搜索引擎，请在`.env`文件中设置`SEARCH_API`变量：

```bash
# 选择一个：tavily, infoquest, duckduckgo, brave_search, arxiv
SEARCH_API=tavily
```

### 爬取工具

- **Jina**（默认）：免费可访问的网页内容爬取工具
  - 无需 API 密钥即可使用基础功能
  - 使用 API 密钥可获得更高的访问速率限制
  - 访问 <https://jina.ai/reader> 了解更多信息

- **InfoQuest**：可选的爬取服务
  - 需要在`.env`文件中设置`INFOQUEST_API_KEY`
  - 提供可配置的爬取参数
  - 支持自定义超时设置

要配置您首选的爬取工具，请在`conf.yaml`文件中设置：

```yaml
CRAWLER_ENGINE:
  # 引擎类型："jina"（默认）或 "infoquest"
  engine: infoquest
```

### 私域知识库引擎

TaskPilot 支持基于私有域知识的检索，您可以将文档上传到多种私有知识库中，以便在研究过程中使用，当前支持的私域知识库有：

- **[RAGFlow](https://ragflow.io/docs/dev/)**：开源的基于检索增强生成的知识库引擎
   ```
   # 参照示例进行配置 .env.example
   RAG_PROVIDER=ragflow
   RAGFLOW_API_URL="http://localhost:9388"
   RAGFLOW_API_KEY="ragflow-xxx"
   RAGFLOW_RETRIEVAL_SIZE=10
   ```

- **[MOI]**：AI 原生多模态数据智能平台
   ```
   # 参照示例进行配置 .env.example
   RAG_PROVIDER=moi
   MOI_API_URL="https://freetier-01.cn-hangzhou.cluster.matrixonecloud.cn"
   MOI_API_KEY="xxx-xxx-xxx-xxx"
   MOI_RETRIEVAL_SIZE=10
   MOI_LIST_LIMIT=10
   ```

- **VikingDB 知识库**：可选的向量知识库服务
   > 按 `.env.example` 填写对应的 API 地址与密钥
   ```
   # 参照示例进行配置 .env.example
   RAG_PROVIDER=vikingdb_knowledge_base
   VIKINGDB_KNOWLEDGE_BASE_API_URL="api-knowledgebase.mlp.cn-beijing.volces.com"
   VIKINGDB_KNOWLEDGE_BASE_API_AK="your-ak-xxx"
   VIKINGDB_KNOWLEDGE_BASE_API_SK="your-sk-xxx"
   VIKINGDB_KNOWLEDGE_BASE_RETRIEVAL_SIZE=15
   ```

## 文本转语音

TaskPilot 现在包含一个文本转语音 (TTS) 功能，允许您将生成的文本转换为语音。速度、音量和音调等特性也可以自定义。

### 使用 TTS API

您可以通过`/api/tts`端点访问 TTS 功能：

```bash
# 使用curl的API调用示例
curl --location 'http://localhost:8000/api/tts' \
--header 'Content-Type: application/json' \
--data '{
    "text": "这是文本转语音功能的测试。",
    "speed_ratio": 1.0,
    "volume_ratio": 1.0,
    "pitch_ratio": 1.0
}' \
--output speech.mp3
```

## Docker

您也可以使用 Docker 运行此项目。

首先，您需要阅读下面的[配置](#配置)部分。确保`.env`和`.conf.yaml`文件已准备就绪。

其次，构建您自己的 Web 服务器 Docker 镜像：

```bash
docker build -t task-pilot-api .
```

最后，启动运行 Web 服务器的 Docker 容器：

```bash
# 将task-pilot-api-app替换为您首选的容器名称
# 启动服务器并绑定到localhost:8000
docker run -d -t -p 127.0.0.1:8000:8000 --env-file .env --name task-pilot-api-app task-pilot-api

# 停止服务器
docker stop task-pilot-api-app
```

### Docker Compose

您也可以使用 docker compose 同时运行后端和前端。

#### 配置

构建前，先配置根目录的 `.env` 文件（从 `.env.example` 复制）：

```bash
cp .env.example .env
cp conf.yaml.example conf.yaml
```

> [!IMPORTANT]
> `docker-compose.yml` 只使用**根目录的 `.env`** 文件（不使用 `web/.env`）。使用 Docker Compose 时，您**不需要**创建或修改 `web/.env`。

如果您在**远程服务器**上部署或通过**局域网 IP**（非 `localhost`）访问，**必须**将根目录 `.env` 中的 `NEXT_PUBLIC_API_URL` 修改为实际的主机 IP 或域名：

```bash
# 示例：通过局域网 IP 访问
NEXT_PUBLIC_API_URL=http://192.168.1.100:8000/api

# 示例：使用域名的远程部署
NEXT_PUBLIC_API_URL=https://your-domain.com/api
```

> [!NOTE]
> `NEXT_PUBLIC_API_URL` 是 Next.js 的**构建时**变量——它会在 `docker compose build` 时被嵌入到前端 JavaScript 包中。如果之后修改了此值，必须重新执行 `docker compose build` 才能生效。

#### 构建和运行

```bash
# 构建docker镜像
docker compose build

# 启动服务器
docker compose up
```

> [!WARNING]
> 如果您想将 TaskPilot 部署到生产环境中，请为网站添加身份验证，并评估 MCPServer 和 Python Repl 的安全检查。

## 开发

### 测试

运行测试套件：

```bash
# 运行所有测试
make test

# 运行特定测试文件
pytest tests/integration/test_workflow.py

# 运行覆盖率测试
make coverage
```

### 代码质量

```bash
# 运行代码检查
make lint

# 格式化代码
make format
```

### 使用 LangGraph Studio 进行调试

TaskPilot 使用 LangGraph 作为其工作流架构。您可以使用 LangGraph Studio 实时调试和可视化工作流。

#### 本地运行 LangGraph Studio

TaskPilot 包含一个`langgraph.json`配置文件，该文件定义了 LangGraph Studio 的图结构和依赖关系。该文件指向项目中定义的工作流图，并自动从`.env`文件加载环境变量。

##### Mac

```bash
# 如果您没有uv包管理器，请安装它
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖并启动LangGraph服务器
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev --allow-blocking
```

##### Windows / Linux

```bash
# 安装依赖
pip install -e .
pip install -U "langgraph-cli[inmem]"

# 启动LangGraph服务器
langgraph dev
```

启动 LangGraph 服务器后，您将在终端中看到几个 URL：

- API: <http://127.0.0.1:2024>
- Studio UI: <https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024>
- API 文档：<http://127.0.0.1:2024/docs>

在浏览器中打开 Studio UI 链接以访问调试界面。

#### 使用 LangGraph Studio

在 Studio UI 中，您可以：

1. 可视化工作流图并查看组件如何连接
2. 实时跟踪执行情况，了解数据如何在系统中流动
3. 检查工作流每个步骤的状态
4. 通过检查每个组件的输入和输出来调试问题

### 启用 LangSmith 追踪

TaskPilot 支持 LangSmith 追踪功能，帮助您调试和监控工作流。要启用 LangSmith 追踪：

1. 确保您的 `.env` 文件中有以下配置（参见 `.env.example`）：

   ```bash
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
   LANGSMITH_API_KEY="xxx"
   LANGSMITH_PROJECT="xxx"
   ```

2. 通过运行以下命令本地启动 LangSmith 追踪：

   ```bash
   langgraph dev
   ```

这将在 LangGraph Studio 中启用追踪可视化，并将您的追踪发送到 LangSmith 进行监控和分析。

## 常见问题

请参阅[FAQ.md](docs/FAQ.md)获取更多详情。

## 许可证

本项目是开源的，遵循[MIT 许可证](./LICENSE)。

## 致谢

TaskPilot 在 Plan-Execute / DeepResearch 工作流之上重新抽象了 Task Runtime：研究图是一种 Workflow；Task/Event、Middleware、Tool Registry、Skill、Memory、Observability、Evaluation 和进程隔离才是 Runtime。

感谢以下开源项目：

- **[LangChain](https://github.com/langchain-ai/langchain)**：LLM 接口、Agent 与工具调用。
- **[LangGraph](https://github.com/langchain-ai/langgraph)**：内置图所用的有状态工作流执行。
- **[Novel](https://github.com/steven-tey/novel)**：报告后期编辑所用的类 Notion 编辑器。
- **[RAGFlow](https://github.com/infiniflow/ragflow)**：私有知识库检索。
