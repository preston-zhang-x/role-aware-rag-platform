# Role Aware RAG Platform

一个面向企业内部知识库的角色感知 RAG 平台，核心是在检索入口完成权限过滤，让用户只能召回自己角色可访问的文档内容。

项目重点解决复杂日式 Excel 式样书的结构化解析问题，并结合向量检索、BM25、RRF 融合与 rerank，提供带来源追溯的问答结果。
![System Architecture](docs/assets/system-architecture.jpg)

## 项目亮点

- 角色感知检索：按 `allowed_roles` 在检索前过滤，支持 `admin / manager / staff`
- 多检索策略：支持 `vector`、`bm25`、`hybrid`、`hybrid_rerank`
- 文档解析增强：针对 `.xlsx` / `.xlsm` / `.xls` / `.xlsb` / `.pdf` 提供统一加载与降级解析
- Excel 式样书优化：保留 Sheet 语义、展开合并单元格、区分 KV 区与表格区
- 可追溯回答：RAG 返回回答正文、命中来源、分块位置与 token/耗时元数据
- 前后端分离：后端 `FastAPI`，前端 `React + Vite`
- 可本地化部署：默认使用 `Ollama + BGE-M3 + 本地 rerank-adapter`

## 为什么做自定义 Excel Parser

很多日式式样书本质上是用 Excel 排版的设计文档，和标准数据表差别很大。直接抽文本虽然能拿到内容，但章节、字段、说明区和表格区的关系很容易丢失。

这里的 parser 会保留人阅读式样书时依赖的结构信息，让后续 chunking、BM25 命中和来源引用都更稳定。

<table>
  <tr>
    <td width="50%" valign="top" align="center">
      <strong>微软开源转换工具MarkItDown 直接转换</strong>
    </td>
    <td width="50%" valign="top" align="center">
      <strong>自定义 Excel Parser</strong>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/excel-markitdown-output.png" alt="MarkItDown converting Excel into a noisy table with many Unnamed columns and NaN values" />
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/excel-custom-parser-output.png" alt="Custom Excel parser preserving readable headings, fields, and sections" />
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <sub>复杂 Excel 式样书里容易出现 <code>Unnamed</code> 列、<code>NaN</code> 和说明区/表格区混杂的问题。</sub>
    </td>
    <td width="50%" valign="top">
      <sub>保留字段名、章节层级、条目关系和可读结构，后续 chunking、BM25 检索和来源引用会更稳。</sub>
    </td>
  </tr>
</table>


- `MarkItDown` 适合通用文档抽取，但复杂 Excel 式样书里的结构容易变成平铺文本或噪声表格
- 自定义 parser 会识别 `Sheet` 语义、KV 区、表格区和合并单元格，输出更接近设计文档原始阅读顺序的文本
- 结构稳定以后，chunk 质量、关键词命中率和回答引用的可读性都会更好

## 动画演示
![动画演示](docs/动画演示.gif)


## 检索模式说明

通过 `.env` 中的 `RETRIEVAL_MODE` 切换：

| 模式            | 说明                     | 适合场景                 |
| --------------- | ------------------------ | ------------------------ |
| `vector`        | 纯向量检索               | 语义相似召回优先         |
| `bm25`          | 纯关键词检索             | 编号、字段名、精确词命中 |
| `hybrid`        | 向量 + BM25，经 RRF 融合 | 平衡召回                 |
| `hybrid_rerank` | `hybrid` 后再做 rerank   | 更高精度上限             |

## 正确率测评

在 RAGBench `emanual` 子集上做离线评测。默认 `hybrid_rerank` 模式下共评测 `132` 个问题：

| 指标 | 结果 |
| --- | --- |
| Accuracy | `90.9%` |
| Source Hit Rate | `100.0%` |
| Avg Source Recall | `0.833` |
| Avg Answer Token F1 | `0.520` |

详细评测结果见 [`docs/report_ragbench_emanual_hybrid_rerank.md`](docs/report_ragbench_emanual_hybrid_rerank.md)。

![Snipaste_2026-04-29_18-29-00](docs/assets/Snipaste_2026-04-29_18-29-00.png)

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

需要先准备这些环境：

- Python `3.11`
- `uv`
- Docker / Docker Compose
- Ollama
- Node.js 与 `npm`（如果需要启动前端）

### 2. 复制环境变量

```powershell
Copy-Item .env.example .env
```

本地开发可直接从下面这组配置开始：

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

- 不使用 Ollama 时，换成兼容 OpenAI API 的模型服务即可；`/v1/models` 需要能返回 `CHAT_MODEL` 与 `EMBEDDING_MODEL`
- 模型会输出思考过程时，保持 `CHAT_THINK=false`，避免响应变慢
- 当 `RETRIEVAL_MODE=hybrid_rerank` 时，`RERANK_*` 配置必须有效
- 默认 preset 会在 `hybrid_rerank` 阶段先扩大候选集，再把 rerank 结果交给最终裁剪；生成阶段仍只使用 `TOP_K=5`

### 3. 安装依赖

使用默认 `hybrid_rerank` 路径时：

```powershell
uv sync --extra rerank
npm --prefix frontend install
```

只跑不带 rerank 的模式时：

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

使用仓库默认的本地模型方案时，先设置 Ollama 参数：

```powershell
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:OLLAMA_NUM_PARALLEL="1"
```

确认 Ollama 已运行：

```powershell
ollama serve
```

拉取模型：

```powershell
ollama pull qwen3.5:4b
ollama pull bge-m3
```

### 6. 启动 rerank-adapter

仅当 `RETRIEVAL_MODE=hybrid_rerank` 时需要：

```powershell
uv run python script/run_rerank_adapter.py
```

启动后可以检查：

- `GET http://localhost:8090/health`
- `POST http://localhost:8090/rerank`

首次启动会下载 `BAAI/bge-reranker-v2-m3`，耗时取决于网络和机器环境。

### 7. 重建向量库并导入文档

`bge-m3` 的向量维度是 `1024`。如果之前用过其他 embedding 模型，先重建 collection：

```powershell
uv run python script/reset_qdrant_collection.py --collection documents
```

导入仓库中的 Excel 文档：

```powershell
uv run python script/ingest_repo_spec.py --dir docs --pattern *.xlsx --recursive
```

也可以导入单个文件：

```powershell
uv run python script/ingest_repo_spec.py --file "docs\\設計_処理設計書_excel_parser.xlsx"
```

注意：

- `script/ingest_repo_spec.py` 会把导入文档的 `allowed_roles` 写成 `admin / manager / staff`
- 验证角色隔离时，需要在自定义导入流程中给不同文档传入不同的 `allowed_roles`

### 8. 创建初始登录用户

首次登录前需要先创建用户。

先生成 bcrypt 密码哈希：

```powershell
uv run python -c "from app.core.security import hash_password; print(hash_password('123456'))"
```

把输出的哈希写入数据库，例如用 `psql` 或 pgAdmin 执行：

```sql
INSERT INTO users (username, hashed_password, role)
VALUES
  ('admin_demo', '<PUT_HASH_HERE>', 'admin'),
  ('manager_demo', '<PUT_HASH_HERE>', 'manager'),
  ('staff_demo', '<PUT_HASH_HERE>', 'staff');
```

`role` 可选值：

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

开发模式下，前端会把 `/api` 和 `/openapi.json` 代理到 `http://127.0.0.1:8000`，不需要额外配置 `VITE_API_BASE_URL`。

启动后访问：

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

返回字段：

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

写入 Qdrant 的分块会带上这些 metadata：

- `source_file`
- `source_key`
- `allowed_roles`
- `chunk_index`
- `sheet_name`
- `cell_range`
- `content_type`

RAG 检索阶段会根据 `allowed_roles` 构造过滤条件，角色隔离在检索入口完成。

## 前端说明

前端包含两个核心页面：

- `/login`：账号密码登录
- `/chat`：提问、查看回答、查看命中来源与耗时元数据

开发模式通过 Vite 代理转发后端请求，前后端可以分别启动。

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
