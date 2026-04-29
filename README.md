# Role Aware RAG Platform

一个面向企业内部知识库问答场景的全栈 RAG 项目。
这个仓库的重点不是“先回答，再补权限”，而是“先按角色过滤，再检索和生成”，尽量从检索入口就避免越权内容进入上下文。

项目当前对日式 Excel 式样书做了专门处理，适合方眼纸风格、表格与说明混排、合并单元格较多的设计文档。
![System Architecture](docs/assets/system-architecture.jpg)
## 项目亮点

- 角色感知检索：基于 `allowed_roles` 做检索前过滤，支持 `admin / manager / staff`
- 多检索策略：支持 `vector`、`bm25`、`hybrid`、`hybrid_rerank`
- 文档解析增强：针对 `.xlsx` / `.xlsm` / `.xls` / `.xlsb` / `.pdf` 提供统一加载与降级解析
- Excel 式样书优化：保留 Sheet 语义、展开合并单元格、区分 KV 区与表格区
- 可追溯回答：RAG 返回回答正文、命中来源、分块位置与 token/耗时元数据
- 前后端分离：后端 `FastAPI`，前端 `React + Vite`
- 可本地化部署：默认使用 `Ollama + BGE-M3 + 本地 rerank-adapter`

## 检索模式说明

通过 `.env` 中的 `RETRIEVAL_MODE` 切换：

| 模式            | 说明                     | 适合场景                 |
| --------------- | ------------------------ | ------------------------ |
| `vector`        | 纯向量检索               | 语义相似召回优先         |
| `bm25`          | 纯关键词检索             | 编号、字段名、精确词命中 |
| `hybrid`        | 向量 + BM25，经 RRF 融合 | 平衡召回                 |
| `hybrid_rerank` | `hybrid` 后再做 rerank   | 更高精度上限             |

## 正确率测评
![Snipaste_2026-04-29_18-29-00](docs\assets\Snipaste_2026-04-29_18-29-00.png)

## 技术栈

| 层 | 组件 |
| --- | --- |
| Backend | `FastAPI`、`SQLAlchemy`、`Alembic` |
| Retrieval | `Qdrant`、`BM25`、`RRF`、本地 `reranker` |
| AI | `OpenAI-compatible API`、默认 `Ollama`、`BGE-M3`、`qwen3.5:4b` |
| Parsing | `openpyxl`、`pdfplumber`、`markitdown` |
| Frontend | `React 19`、`Vite`、`TanStack Query`、`React Router`、`Tailwind CSS` |
| Infra | `PostgreSQL`、`Docker Compose` |

## 目录结构

```text
.
├─ app/                 后端应用
│  ├─ api/v1/           auth / docs / rag / health 接口
│  ├─ core/             配置、鉴权、日志、错误处理
│  ├─ db/               SQLAlchemy 模型与数据库连接
│  ├─ clients/          Qdrant 客户端封装
│  └─ services/         解析、导入、检索、RAG、rerank 等核心逻辑
├─ frontend/            React 前端（登录页 + 聊天页）
├─ script/              导入、评测、Qdrant 重置、rerank 启动脚本
├─ docs/                设计文档、式样书
├─ out/                 生成产物与图示
├─ tests/               单元测试与集成测试
├─ alembic/             数据库迁移
├─ docker-compose.yml   PostgreSQL / Qdrant / pgAdmin
└─ .env.example         环境变量示例
```

## 默认端口

| 服务 | 地址 |
| --- | --- |
| FastAPI | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| Frontend | `http://127.0.0.1:5173` |
| PostgreSQL | `localhost:5434` |
| pgAdmin | `http://127.0.0.1:5050` |
| Qdrant HTTP | `http://127.0.0.1:6333` |
| Qdrant gRPC | `localhost:6334` |
| Ollama | `http://localhost:11434` |
| rerank-adapter | `http://localhost:8090` |

## 快速开始

### 1. 环境准备

建议先准备好以下基础环境：

- Python `3.11`
- `uv`
- Docker / Docker Compose
- Ollama
- Node.js 与 `npm`（如果需要启动前端）

### 2. 复制环境变量

```powershell
Copy-Item .env.example .env
```

本地默认推荐配置如下：

```env
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_db
DATABASE_URL=postgresql+psycopg2://your_user:your_password@localhost:5434/your_db

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

SECRET_KEY=long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
CHAT_MODEL=qwen3.5:4b
CHAT_THINK=false
CHAT_TEMPERATURE=0.0
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSIONS=1024

RETRIEVAL_MODE=hybrid_rerank
TOP_K=5
SCORE_THRESHOLD=0.01

RERANK_BASE_URL=http://localhost:8090
RERANK_API_KEY=local-rerank
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_TIMEOUT_SECONDS=8
RERANK_CANDIDATE_TOP_K=40
RERANK_RETURN_TOP_N=15
RERANK_MAX_TOKENS_PER_DOC=1024
```

说明：

- 如果你不是用 Ollama，只要模型服务兼容 OpenAI API，并且 `/v1/models` 能返回 `CHAT_MODEL` 与 `EMBEDDING_MODEL` 即可
- 如果使用带思考链的模型，建议保持 `CHAT_THINK=false`，减少响应响应时间
- 当 `RETRIEVAL_MODE=hybrid_rerank` 时，`RERANK_*` 配置必须有效
- 当前默认 preset 会让 `hybrid_rerank` 先扩大候选，再返回更大的 rerank 窗口给最终裁剪；生成阶段仍只保留 `TOP_K=5`

### 3. 安装依赖

如果你使用默认 `hybrid_rerank` 路径：

```powershell
uv sync --extra rerank
npm --prefix frontend install
```

如果暂时只想跑不带 rerank 的模式：

```powershell
uv sync
npm --prefix frontend install
```

### 4. 启动基础依赖

```powershell
docker compose up -d db qdrant
uv run alembic upgrade head
```

### 5. 启动 Ollama 并拉取模型

如果你使用仓库默认本地模型方案，先设置 Ollama 相关参数：

```powershell
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:OLLAMA_NUM_PARALLEL="1"
```

然后确认 Ollama 已运行：

```powershell
ollama serve
```

再拉取模型：

```powershell
ollama pull qwen3.5:4b
ollama pull bge-m3
```

### 6. 启动 rerank-adapter

仅当 `RETRIEVAL_MODE=hybrid_rerank` 时需要：

```powershell
uv run python script/run_rerank_adapter.py
```

启动后可检查：

- `GET http://localhost:8090/health`
- `POST http://localhost:8090/rerank`

首次启动时会下载 `BAAI/bge-reranker-v2-m3`，可能需要等待一段时间。

### 7. 重建向量库并导入文档

切换到 `bge-m3` 后，向量维度为 `1024`。如果你之前用过别的 embedding 模型，建议先重建 collection：

```powershell
uv run python script/reset_qdrant_collection.py --collection documents
```

然后导入仓库中的 Excel 文档：

```powershell
uv run python script/ingest_repo_spec.py --dir docs --pattern *.xlsx --recursive
```

也可以只导入单个文件：

```powershell
uv run python script/ingest_repo_spec.py --file "docs\\設計_処理設計書_excel_parser.xlsx"
```

注意：

- 当前 `script/ingest_repo_spec.py` 默认会把导入文档的 `allowed_roles` 写成 `admin / manager / staff`
- 如果你要验证真正的角色隔离效果，需要在自定义导入流程中传入不同的 `allowed_roles`

### 8. 创建初始登录用户

首次登录前需要手动创建用户。

先生成 bcrypt 密码哈希：

```powershell
uv run python -c "from app.core.security import hash_password; print(hash_password('123456'))"
```

然后把输出的哈希写入数据库，例如使用 `psql` 或 pgAdmin 执行：

```sql
INSERT INTO users (username, hashed_password, role)
VALUES
  ('admin_demo', '<PUT_HASH_HERE>', 'admin'),
  ('manager_demo', '<PUT_HASH_HERE>', 'manager'),
  ('staff_demo', '<PUT_HASH_HERE>', 'staff');
```

其中 `role` 只能是：

- `admin`
- `manager`
- `staff`

### 9. 启动后端与前端

后端：

```powershell
uv run uvicorn app.main:app --reload
```

前端：

```powershell
npm --prefix frontend run dev
```

开发模式下，前端会把 `/api` 和 `/openapi.json` 代理到 `http://127.0.0.1:8000`，默认不需要额外配置 `VITE_API_BASE_URL`。

启动后可以访问：

- 后端文档：`http://127.0.0.1:8000/docs`
- 前端页面：`http://127.0.0.1:5173/login`
- 聊天页面：登录后跳转到 `http://127.0.0.1:5173/chat`

## API 概览

### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 表单登录，返回 JWT |
| `GET` | `/api/v1/auth/me` | 获取当前用户 |

`/api/v1/auth/login` 使用 `OAuth2PasswordRequestForm`，所以请求体需要是 `application/x-www-form-urlencoded`。

登录示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin_demo&password=123456"
```

### RAG

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/rag/ask` | 基于当前登录角色执行检索问答 |

示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/rag/ask" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"FN-007 的功能名是什么？\"}"
```

返回内容包含：

- `answer`
- `sources[]`
- `metadata.latency_ms`
- `metadata.prompt_tokens`
- `metadata.completion_tokens`
- `metadata.total_tokens`

## 文档解析与导入说明

### 支持格式

- `.xlsx` / `.xlsm`：优先使用 `JapaneseExcelParser`
- `.xls` / `.xlsb`：直接走 `MarkItDownFallback`
- `.pdf`：优先使用 `PDFMarkdownParser`

### Excel 解析特性

- 按 Sheet 注入一级标题，保留章节语义
- 展开合并单元格，减少信息丢失
- 启发式区分文本块、KV 区、表格区
- 保留 `sheet_name`、`cell_range`、`content_type`
- 跳过隐藏 Sheet，并输出 warning
- 当公式没有缓存值时保留公式文本并记录 warning

### 导入后的关键 metadata

写入 Qdrant 的分块会带上这类 metadata：

- `source_file`
- `source_key`
- `allowed_roles`
- `chunk_index`
- `sheet_name`
- `cell_range`
- `content_type`

RAG 检索阶段会基于 `allowed_roles` 构造过滤条件，因此角色隔离发生在检索入口。

## 前端说明

前端当前提供两个核心页面：

- `/login`：账号密码登录
- `/chat`：提问、查看回答、查看命中来源与耗时元数据

开发模式使用 Vite 代理转发后端请求，因此前后端可以分别独立启动。

## 测试

### 运行测试

```powershell
uv run pytest
```

前端代码检查：

```powershell
npm --prefix frontend run lint
```

## License

本项目采用 [`MIT`](./LICENSE) 许可证。
