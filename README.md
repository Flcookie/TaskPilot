# TaskPilot

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/Flcookie/TaskPilot/actions/workflows/lint.yaml/badge.svg)](https://github.com/Flcookie/TaskPilot/actions)

[English](./README.md) | [简体中文](./README_zh.md)

**TaskPilot** is a lightweight Agent Runtime for complex task execution.

Every request is an explicit **Task**: create, run, interrupt, resume, cancel, replay, and evaluate. Events are persisted and streamed over SSE. Skills, tools, memory, and middleware sit around the execution engine — they are not baked into a single research graph.

The bundled Plan-Execute / DeepResearch graph is one **Workflow** on this runtime. Reports, podcasts, and slides are workflow outputs, not the product itself.

## Contents

- [Architecture](#architecture)
- [Runtime](#runtime)
- [Features](#features)
- [Getting started](#getting-started)
- [Search, crawl, and knowledgebase](#search-crawl-and-knowledgebase)
- [Text-to-speech](#text-to-speech)
- [Docker](#docker)
- [Development](#development)
- [FAQ](#faq)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Architecture

```
Client (Web UI / CLI)
        │
        ▼
FastAPI
  /api/tasks*           explicit task lifecycle
  /api/chat/stream      compatible streaming entry
        │
        ▼
TaskPilot Runtime
  TaskService · EventStore · Middleware · ToolRegistry
  Skill (lazy load) · Memory · Evaluation · process isolation
        │
        ▼
LangGraph Workflows
  DeepResearch · podcast · presentation · …
        │
        ▼
TaskEvent log  →  SSE live / replay (?task=) / evaluate
```

The runtime owns lifecycle, observability, and policy. LangGraph owns graph execution. `/api/chat/stream` remains a compatible entry; new work should go through `/api/tasks`.

## Runtime

### Task lifecycle

Statuses: `pending` → `running` → `interrupted` | `succeeded` | `failed` | `cancelled`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/tasks` | Create a task (default workflow: `deep_research`) |
| `GET` | `/api/tasks/{id}` | Status and metadata |
| `GET` | `/api/tasks/{id}/events` | Persisted event log (`after_seq` for paging) |
| `GET` | `/api/tasks/{id}/stream` | Start or continue SSE (`Last-Event-ID` for resume) |
| `POST` | `/api/tasks/{id}/cancel` | Cancel a running or pending task |
| `POST` | `/api/tasks/{id}/resume` | Resume after interrupt / failure |
| `POST` | `/api/tasks/{id}/replay` | Replay stored events as SSE |
| `POST` | `/api/tasks/{id}/evaluate` | Process + report + skill-loading scores |

Web replay: open `http://localhost:3000/chat?task=<task_id>`.

Task and event persistence defaults to SQLite (`TASK_STORE_URL=sqlite:///data/tasks.sqlite`). Tests use `memory://`.

### Middleware

Hooks are subscription points (`before_task`, `before_tool`, `after_llm`, `on_error`, …). Default stack:

`audit → skill → context_inject → token_accounting → tool_guard → memory_write`

Memory is a store, not a middleware. `context_inject` writes retrieved memory into prompts; `memory_write` persists new facts asynchronously.

### Skill

A Skill is a reusable execution policy: description, tags, and `allowed_tools` (the **visible** tool set for that run). Skills load lazily; v1 does not compose skills.

| Skill | When to use |
|---|---|
| `deep_research` | Multi-source investigation and reports |
| `data_analysis` | Numbers, comparison, Python-heavy work |
| `report_writing` | Structure existing material into a document |

### Memory

Three layers: **preference**, **background**, **fact**. Default store: `MEMORY_STORE_URL=sqlite:///data/memory.sqlite`.

### Evaluation and isolation

- **Process metrics**: plan quality, tool choice, recovery from failure
- **Report metrics**: existing report-quality judge
- **Skill loading compare**: token/latency with vs without lazy skill load
- **Python isolation**: code runs in a subprocess. This is process isolation, not a security sandbox.

## Features

### Runtime

- Explicit Task objects with event logs, SSE resume, and replay
- Hook-based middleware (audit, skill policy, token accounting, tool guard)
- Unified `ToolRegistry` + `ToolResult` contract for built-in tools and MCP
- Skill lazy load with per-skill `allowed_tools`
- Long-term memory (preference / background / fact)
- Agent evaluation (process + report + skill loading)
- LLM via [litellm](https://docs.litellm.ai/docs/providers), including OpenAI-compatible and open-source models such as Qwen — see [configuration](docs/configuration_guide.md)

### Tools and MCP

- 🔍 **Search and retrieval** — Tavily, InfoQuest, Brave Search, crawl (Jina / InfoQuest), private knowledge bases
- 📃 **RAG** — [Qdrant](https://qdrant.tech/), [Milvus](https://milvus.io/), [RAGFlow](https://github.com/infiniflow/ragflow), VikingDB, MOI, Dify; mention files from RAG providers in the input box
- 🔗 **MCP** — extra tools for private APIs, knowledge graphs, browsing, and more

### Human collaboration

- 💬 **Clarification** — multi-turn questions before a vague task is planned ([guide](./docs/configuration_guide.md#multi-turn-clarification-feature))
- 🧠 **Human-in-the-loop** — accept or edit the plan in natural language, or auto-accept
- 📝 **Report editing** — Notion-like blocks with AI polish / shorten / expand ([tiptap](https://tiptap.dev/))

### Workflow outputs

- 🎙️ **Podcast and presentation** — script + TTS audio, and simple PowerPoint from the same task run

## Getting started

TaskPilot is developed in Python, and comes with a web UI written in Node.js. To ensure a smooth setup process, we recommend using the following tools:

### Recommended Tools

- **[`uv`](https://docs.astral.sh/uv/getting-started/installation/):**
  Simplify Python environment and dependency management. `uv` automatically creates a virtual environment in the root directory and installs all required packages for you—no need to manually install Python environments.

- **[`nvm`](https://github.com/nvm-sh/nvm):**
  Manage multiple versions of the Node.js runtime effortlessly.

- **[`pnpm`](https://pnpm.io/installation):**
  Install and manage dependencies of Node.js project.

### Environment Requirements

Make sure your system meets the following minimum requirements:

- **[Python](https://www.python.org/downloads/):** Version `3.12+`
- **[Node.js](https://nodejs.org/en/download/):** Version `22+`

### Installation

```bash
# Clone the repository
git clone https://github.com/Flcookie/TaskPilot.git
cd TaskPilot

# Install dependencies, uv will take care of the python interpreter and venv creation, and install the required packages
uv sync

# Configure .env with your API keys
# Tavily: https://app.tavily.com/home
# Brave_SEARCH: https://brave.com/search/api/
# TTS: Add your TTS credentials if you have them
cp .env.example .env

# See the 'Supported Search Engines' and 'Text-to-Speech Integration' sections below for all available options

# Configure conf.yaml for your LLM model and API keys
# Please refer to 'docs/configuration_guide.md' for more details
# For local development, you can use Ollama or other local models
cp conf.yaml.example conf.yaml

# Install marp for ppt generation
# https://github.com/marp-team/marp-cli?tab=readme-ov-file#use-package-manager
brew install marp-cli
```

Optionally, install web UI dependencies via [pnpm](https://pnpm.io/installation):

```bash
cd web
pnpm install
```

### Configurations

Please refer to the [Configuration Guide](docs/configuration_guide.md) for more details.

> [!NOTE]
> Before you start the project, read the guide carefully, and update the configurations to match your specific settings and requirements.

Task and memory stores default to SQLite so replay and long-term memory survive a restart. Override in `.env` if needed:

```bash
TASK_STORE_URL=sqlite:///data/tasks.sqlite
MEMORY_STORE_URL=sqlite:///data/memory.sqlite
# TASK_STORE_URL=memory://
# MEMORY_STORE_URL=memory://
```

### Console UI

The quickest way to run the project is to use the console UI.

```bash
# Run the project in a bash-like shell
uv run main.py
```

### Web UI

This project also includes a Web UI, offering a more dynamic and engaging interactive experience.

> [!NOTE]
> You need to install the dependencies of web UI first.

```bash
# Run both the backend and frontend servers in development mode
# On macOS/Linux
./bootstrap.sh -d

# On Windows
bootstrap.bat -d
```
> [!Note]
> By default, the backend server binds to 127.0.0.1 (localhost) for security reasons. If you need to allow external connections (e.g., when deploying on Linux server), you can modify the server host to 0.0.0.0 in the bootstrap script(uv run server.py --host 0.0.0.0).
> Please ensure your environment is properly secured before exposing the service to external networks.

Open your browser and visit [`http://localhost:3000`](http://localhost:3000) to explore the web UI.

Replay a finished run with `http://localhost:3000/chat?task=<task_id>`.

Explore more details in the [`web`](./web/) directory.

### Task API

After the backend is up (`http://localhost:8000`):

```bash
# Create a task (DeepResearch is the default workflow)
curl -s -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What is MCP?"}],"auto_accepted_plan":true}'

# Stream execution (replace TASK_ID)
curl -N http://localhost:8000/api/tasks/TASK_ID/stream
```

See [Runtime](#runtime) for cancel / resume / replay / evaluate.

## Search, crawl, and knowledgebase

### Web Search

TaskPilot supports multiple search engines that can be configured in your `.env` file using the `SEARCH_API` variable:

- **Tavily** (default): A specialized search API for AI applications
  - Requires `TAVILY_API_KEY` in your `.env` file
  - Sign up at: https://app.tavily.com/home

- **InfoQuest**: Optional search and crawling provider
  - Requires `INFOQUEST_API_KEY` in your `.env` file
  - Support for time range filtering and site filtering

- **DuckDuckGo**: Privacy-focused search engine
  - No API key required

- **Brave Search**: Privacy-focused search engine with advanced features
  - Requires `BRAVE_SEARCH_API_KEY` in your `.env` file
  - Sign up at: https://brave.com/search/api/

- **Arxiv**: Scientific paper search for academic research
  - No API key required
  - Specialized for scientific and academic papers

- **Searx/SearxNG**: Self-hosted metasearch engine
  - Requires `SEARX_HOST` to be set in the `.env` file
  - Supports connecting to either Searx or SearxNG

To configure your preferred search engine, set the `SEARCH_API` variable in your `.env` file:

```bash
# Choose one: tavily, infoquest, duckduckgo, brave_search, arxiv
SEARCH_API=tavily
```

### Crawling Tools

TaskPilot supports multiple crawling tools that can be configured in your `conf.yaml` file:

- **Jina** (default): Freely accessible web content crawling tool

- **InfoQuest**: Optional crawling provider
  - Requires `INFOQUEST_API_KEY` in your `.env` file
  - Provides configurable crawling parameters
  - Supports custom timeout settings

To configure your preferred crawling tool, set the following in your `conf.yaml` file:

```yaml
CRAWLER_ENGINE:
  # Engine type: "jina" (default) or "infoquest"
  engine: infoquest
```

### Private Knowledgebase

TaskPilot supports private knowledgebase such as RAGFlow, Qdrant, Milvus, and VikingDB, so that you can use your private documents to answer questions.

- **[RAGFlow](https://ragflow.io/docs/dev/)**: open source RAG engine
   ```bash
   # examples in .env.example
   RAG_PROVIDER=ragflow
   RAGFLOW_API_URL="http://localhost:9388"
   RAGFLOW_API_KEY="ragflow-xxx"
   RAGFLOW_RETRIEVAL_SIZE=10
   RAGFLOW_CROSS_LANGUAGES=English,Chinese,Spanish,French,German,Japanese,Korean
   ```

- **[Qdrant](https://qdrant.tech/)**: open source vector database
   ```bash
   # Using Qdrant Cloud or self-hosted
   RAG_PROVIDER=qdrant
   QDRANT_LOCATION=https://xyz-example.eu-central.aws.cloud.qdrant.io:6333
   QDRANT_API_KEY=your_qdrant_api_key
   QDRANT_COLLECTION=documents
   QDRANT_EMBEDDING_PROVIDER=openai
   QDRANT_EMBEDDING_MODEL=text-embedding-ada-002
   QDRANT_EMBEDDING_API_KEY=your_openai_api_key
   QDRANT_AUTO_LOAD_EXAMPLES=true
   ```

## Text-to-speech

TaskPilot now includes a Text-to-Speech (TTS) feature that allows you to convert generated text to speech. Speed, volume, and pitch are customizable.

### Using the TTS API

You can access the TTS functionality through the `/api/tts` endpoint:

```bash
# Example API call using curl
curl --location 'http://localhost:8000/api/tts' \
--header 'Content-Type: application/json' \
--data '{
    "text": "This is a test of the text-to-speech functionality.",
    "speed_ratio": 1.0,
    "volume_ratio": 1.0,
    "pitch_ratio": 1.0
}' \
--output speech.mp3
```

## Docker

You can also run this project with Docker.

First, you need to read the [configuration](docs/configuration_guide.md) below. Make sure `.env`, `.conf.yaml` files are ready.

Second, to build a Docker image of your own web server:

```bash
docker build -t task-pilot-api .
```

Finally, start up a docker container running the web server:
```bash
# Replace task-pilot-api-app with your preferred container name
# Start the server then bind to localhost:8000
docker run -d -t -p 127.0.0.1:8000:8000 --env-file .env --name task-pilot-api-app task-pilot-api

# stop the server
docker stop task-pilot-api-app
```

### Docker Compose (include both backend and frontend)

TaskPilot provides a docker-compose setup to easily run both the backend and frontend together.

#### Configuration

Before building, configure the root `.env` file (copied from `.env.example`):

```bash
cp .env.example .env
cp conf.yaml.example conf.yaml
```

> [!IMPORTANT]
> The `docker-compose.yml` only uses the **root `.env`** file (not `web/.env`). You do **not** need to create or modify `web/.env` when using Docker Compose.

If you are deploying on a **remote server** or accessing from a **LAN IP** (not `localhost`), you **must** update `NEXT_PUBLIC_API_URL` in the root `.env` to your actual host IP or domain:

```bash
# Example: accessing from LAN IP
NEXT_PUBLIC_API_URL=http://192.168.1.100:8000/api

# Example: remote deployment with domain
NEXT_PUBLIC_API_URL=https://your-domain.com/api
```

> [!NOTE]
> `NEXT_PUBLIC_API_URL` is a **build-time** variable for Next.js — it gets embedded into the frontend JavaScript bundle during `docker compose build`. If you change this value later, you must rebuild with `docker compose build` for the change to take effect.

#### Build and Run

```bash
# building docker image
docker compose build

# start the server
docker compose up
```

> [!WARNING]
> If you want to deploy the deer flow into production environments, please add authentication to the website and evaluate your security check of the MCPServer and Python Repl.

## Development

### Testing
Install development dependencies:

```bash
uv pip install -e ".[test]"
```

Run the test suite:

```bash
# Run all tests
make test

# Run specific test file
pytest tests/integration/test_workflow.py

# Run with coverage
make coverage
```

### Code Quality

```bash
# Run linting
make lint

# Format code
make format
```

### Debugging with LangGraph Studio

TaskPilot uses LangGraph for its workflow architecture. You can use LangGraph Studio to debug and visualize the workflow in real-time.

#### Running LangGraph Studio Locally

TaskPilot includes a `langgraph.json` configuration file that defines the graph structure and dependencies for the LangGraph Studio. This file points to the workflow graphs defined in the project and automatically loads environment variables from the `.env` file.

##### Mac

```bash
# Install uv package manager if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and start the LangGraph server
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev --allow-blocking
```

##### Windows / Linux

```bash
# Install dependencies
pip install -e .
pip install -U "langgraph-cli[inmem]"

# Start the LangGraph server
langgraph dev
```

After starting the LangGraph server, you'll see several URLs in the terminal:

- API: http://127.0.0.1:2024
- Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- API Docs: http://127.0.0.1:2024/docs

Open the Studio UI link in your browser to access the debugging interface.

#### Using LangGraph Studio

In the Studio UI, you can:

1. Visualize the workflow graph and see how components connect
2. Trace execution in real-time to see how data flows through the system
3. Inspect the state at each step of the workflow
4. Debug issues by examining inputs and outputs of each component

### Enabling LangSmith Tracing

TaskPilot supports LangSmith tracing to help you debug and monitor your workflows. To enable LangSmith tracing:

1. Make sure your `.env` file has the following configurations (see `.env.example`):

   ```bash
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
   LANGSMITH_API_KEY="xxx"
   LANGSMITH_PROJECT="xxx"
   ```

2. Start tracing and visualize the graph locally with LangSmith by running:
   ```bash
   langgraph dev
   ```

This will enable trace visualization in LangGraph Studio and send your traces to LangSmith for monitoring and analysis.

### Task event store

Task metadata and SSE events persist independently of LangGraph checkpoints. Default is SQLite (`TASK_STORE_URL`). Replay uses this log (`POST /api/tasks/{id}/replay` or `?task=` in the Web UI), not the LangGraph checkpoint.

### Checkpointing
1. Postgres and MongoDB implementation of LangGraph checkpoint saver (graph state, not the Task event log).
2. In-memory store is used to cache the streaming messages before persisting to database; If finish_reason is "stop" or "interrupt", it triggers persistence.
3. Supports saving and loading checkpoints for workflow execution.
4. Supports saving chat stream events for replaying conversations.

*Note: About langgraph issue #5557*
The latest langgraph-checkpoint-postgres-2.0.23 have checkpointing issue, you can check the open issue: "TypeError: Object of type HumanMessage is not JSON serializable"  [https://github.com/langchain-ai/langgraph/issues/5557].

To use postgres checkpoint, you should install langgraph-checkpoint-postgres-2.0.21

*Note: About psycopg dependencies*
Please read the following document before using postgres:  https://www.psycopg.org/psycopg3/docs/basic/install.html

BY default, psycopg needs libpq to be installed on your system. If you don't have libpq installed, you can install psycopg with the `binary` extra to include a statically linked version of libpq manually:

```bash
pip install psycopg[binary]
```
This will install a self-contained package with all the libraries needed, but binary not supported for all platform, you check the supported platform: https://pypi.org/project/psycopg-binary/#files

If not supported, you can select local-installation: https://www.psycopg.org/psycopg3/docs/basic/install.html#local-installation


The default database and collection will be automatically created if not exists.
Default database: checkpoing_db
Default collection: checkpoint_writes_aio (langgraph checkpoint writes)
Default collection: checkpoints_aio (langgraph checkpoints)
Default collection: chat_streams (chat stream events for replaying conversations)

You need to set the following environment variables in your `.env` file:

```bash
# Enable LangGraph checkpoint saver, supports MongoDB, Postgres
LANGGRAPH_CHECKPOINT_SAVER=true
# Set the database URL for saving checkpoints
LANGGRAPH_CHECKPOINT_DB_URL="mongodb://localhost:27017/"
#LANGGRAPH_CHECKPOINT_DB_URL=postgresql://localhost:5432/postgres
```

## FAQ

Please refer to the [FAQ.md](docs/FAQ.md) for more details.

## License

This project is open source and available under the [MIT License](./LICENSE).

## Acknowledgments

TaskPilot re-abstracts a Task Runtime around a Plan-Execute / DeepResearch workflow: the research graph is a Workflow; Task/Event, Middleware, Tool Registry, Skill, Memory, Observability, Evaluation, and process isolation are the runtime.

We are grateful to the open-source projects this stack builds on:

- **[LangChain](https://github.com/langchain-ai/langchain)**: LLM interfaces, agents, and tool calling.
- **[LangGraph](https://github.com/langchain-ai/langgraph)**: stateful workflow execution used by bundled graphs.
- **[Novel](https://github.com/steven-tey/novel)**: Notion-style editor for report post-editing.
- **[RAGFlow](https://github.com/infiniflow/ragflow)**: private knowledge-base retrieval.
