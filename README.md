# Role Aware RAG Platform

一个带角色权限控制的 RAG 后端项目，适合企业内部知识库问答场景。
对日式 Excel 式样书的解析做了专门处理。

项目重点是“按角色检索”。
用户提问时，系统会先按角色过滤可见文档，再进行召回和回答，避免把不该看到的内容一起带出来。

## 目前功能

- 支持 `admin / manager / staff` 等角色隔离
- 支持 Excel、PDF 文档解析与入库
- 对日式 Excel 式样书做了针对性解析，适合方眼纸风格、表格和说明混排的文档
- 文档切分后写入 Qdrant，供后续检索使用
- 支持 `vector`、`bm25`、`hybrid`、`hybrid_rerank` 四种检索模式
- 提供认证、文档管理、问答 API

## 文档解析特点

- 按 Sheet 组织内容，保留式样书原有章节语义
- 对合并单元格做展开，减少关键信息丢失
- 能区分 KV 说明区和表格区，转成更适合检索的 Markdown
- 会跳过隐藏 Sheet，并保留解析 warning，便于排查数据问题

## 适合的场景

- 企业内部知识库问答
- 不同岗位看到不同内容的问答系统
- 制度、报表、说明书等内部文档检索
- 以日式 Excel 式样书为主的系统设计文档检索

## 技术栈

`FastAPI` + `PostgreSQL` + `Qdrant` + `OpenAI Embedding/LLM` + `BM25`

## 核心点

不是单纯做一个能回答问题的 RAG，而是先把权限边界处理清楚，再做检索和生成。

## 本地模型部署

当前仓库默认按 `BGE-M3 + Ollama + 本地 rerank-adapter` 来接入本地模型：

- Chat: `qwen3:4b`
- Embedding: `bge-m3`
- Reranker: `BAAI/bge-reranker-v2-m3`

推荐的环境变量见 [`.env.example`](./.env.example)。

### 1. 准备 `.env`

如果仓库里还没有 `.env`，先从示例文件复制：

```powershell
Copy-Item .env.example .env
```

然后确认 `.env` 里的以下配置已经改成本地模型方案：

```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
CHAT_MODEL=qwen3:4b
CHAT_THINK=false
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSIONS=1024
RERANK_BASE_URL=http://localhost:8090
RERANK_API_KEY=local-rerank
RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

如果使用 `qwen3.5` 这类带思考能力的模型，建议保持：

```env
CHAT_THINK=false
```

这样 RAG 生成阶段会向 Ollama 传递 `think=false`，减少推理时长和超时概率。

### 2. 安装 Python 依赖

只运行主服务时：

```powershell
uv sync
```

如果要使用默认的 `hybrid_rerank` 模式，再额外安装 rerank sidecar 依赖：

```powershell
uv sync --extra rerank
```

### 3. 启动基础依赖

```powershell
docker compose up -d db qdrant
uv run alembic upgrade head
```

### 4. 启动 Ollama 并拉模型

先设置 Ollama 相关环境变量，再启动或重启 Ollama。
如果 Ollama 已经在后台运行，需要重启后这些变量才会生效。

```powershell
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:OLLAMA_NUM_PARALLEL="1"
```

如果你没有使用桌面版自动启动，可以手动启动服务：

```powershell
ollama serve
```

确认 Ollama 已经运行后，再拉取模型：

```powershell
ollama pull qwen3:4b
ollama pull qwen3:8b
ollama pull bge-m3
```

### 5. 启动 rerank-adapter

如果你保持默认的 `RETRIEVAL_MODE=hybrid_rerank`，这一步必须启动。
如果你手动切到 `vector`、`bm25` 或 `hybrid`，可以先跳过。

启动适配服务：

```powershell
uv run python script/run_rerank_adapter.py
```

服务会监听 `http://localhost:8090`，并提供：

- `GET /health`
- `POST /rerank`

首次启动时，`rerank-adapter` 会从 Hugging Face 下载 `BAAI/bge-reranker-v2-m3`。
第一次启动可能需要等待一段时间，直到 `GET /health` 返回 `status=ok`。

### 6. 重建向量库

切换到 `bge-m3` 后，向量维度会变成 `1024`，需要重建 collection：

```powershell
uv run python script/reset_qdrant_collection.py --collection documents
uv run python script/ingest_repo_spec.py --dir docs --pattern *.xlsx --recursive
```

### 7. 启动主应用

```powershell
uv run uvicorn app.main:app --reload
```

`GET /api/v1/health/ready` 现在会额外检查：

- 数据库
- Qdrant
- OpenAI 兼容模型服务中的 `chat_model` / `embedding_model`
- `rerank-adapter` 的 `/health`（仅 `hybrid_rerank` 模式要求为 `ok`）

### 8. 一次性启动前的最小检查

按默认 `hybrid_rerank` 路径，一次性启动成功至少需要同时满足：

- `.env` 已切到本地模型配置
- `docker compose up -d db qdrant` 已成功
- Ollama 服务正在运行，且已经 `pull` 了 `qwen3:4b` 与 `bge-m3`
- `uv run python script/run_rerank_adapter.py` 已启动，且 `GET http://localhost:8090/health` 返回 `ok`
- 重建过 Qdrant collection，避免旧向量维度与 `bge-m3` 的 `1024` 发生冲突
