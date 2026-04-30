# Role Aware RAG Platform — role-aware RAG for enterprise knowledge bases

面向企业内部知识库的角色感知 RAG 平台，在检索入口完成权限过滤，让每个用户只能召回自己角色可访问的文档内容。

---

<p align="left">
  <a href="./pyproject.toml"><img alt="version" src="https://img.shields.io/badge/version-v0.1.0-0EA5E9?style=flat-square"></a>
  <a href="./LICENSE"><img alt="license" src="https://img.shields.io/badge/license-Apache--2.0-D4A017?style=flat-square"></a>
  <a href="https://github.com/preston-zhang-x/role-aware-rag-platform/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/preston-zhang-x/role-aware-rag-platform/ci.yml?branch=main&label=CI&style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white&style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white&style=flat-square">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111827&style=flat-square">
  <img alt="Qdrant" src="https://img.shields.io/badge/Qdrant-vector%20store-DC244C?style=flat-square">
  <a href="https://github.com/preston-zhang-x/role-aware-rag-platform/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/preston-zhang-x/role-aware-rag-platform?style=social"></a>
</p>

<p align="left">
  <strong>中文</strong> |
  <a href="./README.md">日本語</a> |
  <a href="./README.en.md">English</a>
</p>

---

## 项目概览

Role Aware RAG Platform 是一个面向企业内部知识库的 RAG 应用。它把用户角色、文档权限、混合检索和来源追溯放在同一条问答链路里，适合需要权限隔离的后台系统、社内文档检索、日式设计书问答和本地化 AI 助手。

项目重点解决复杂日式 Excel 式样书的结构化解析问题，并结合向量检索、BM25、RRF 融合与 rerank，提供稳定、可追溯、可本地部署的问答结果。

![System Architecture](docs/assets/system-architecture.jpg)

## 核心能力

- **角色感知检索**：按 `allowed_roles` 在检索前过滤，支持 `admin / manager / staff`
- **多检索策略**：支持 `vector`、`bm25`、`hybrid`、`hybrid_rerank`
- **Excel 式样书优化**：保留 Sheet 语义、展开合并单元格、区分 KV 区与表格区
- **统一文档加载**：支持 `.xlsx`、`.xlsm`、`.xls`、`.xlsb`、`.pdf`
- **可追溯回答**：返回回答正文、命中来源、分块位置、token 与耗时元数据
- **前后端分离**：后端 `FastAPI`，前端 `React + Vite`
- **本地化部署**：默认使用 `Ollama + BGE-M3 + 本地 rerank-adapter`

## 为什么做自定义 Excel Parser

很多日式式样书本质上是用 Excel 排版的设计文档，和标准数据表差别很大。直接抽文本虽然能拿到内容，但章节、字段、说明区和表格区之间的关系很容易丢失。

自定义 parser 会保留人阅读式样书时依赖的结构信息，让后续 chunking、BM25 命中和来源引用都更稳定。

<table>
  <tr>
    <td width="50%" valign="top" align="center">
      <strong>MarkItDown 直接转换</strong>
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

## 动画演示

![动画演示](docs/动画演示.gif)

## 检索模式

通过 `.env` 中的 `RETRIEVAL_MODE` 切换：

| 模式 | 说明 | 适合场景 |
| --- | --- | --- |
| `vector` | 纯向量检索 | 语义相似召回优先 |
| `bm25` | 纯关键词检索 | 编号、字段名、精确词命中 |
| `hybrid` | 向量 + BM25，经 RRF 融合 | 平衡召回 |
| `hybrid_rerank` | `hybrid` 后再做 rerank | 更高精度上限 |

## 正确率测评

在 RAGBench `emanual` 子集上做离线评测。默认 `hybrid_rerank` 模式下共评测 `132` 个问题：

| 指标 | 结果 |
| --- | --- |
| Accuracy | `90.9%` |
| Source Hit Rate | `100.0%` |
| Avg Source Recall | `0.833` |
| Avg Answer Token F1 | `0.520` |

详细评测结果见 [`docs/report_ragbench_emanual_hybrid_rerank.md`](docs/report_ragbench_emanual_hybrid_rerank.md)。

![RAGBench hybrid rerank evaluation](docs/assets/Snipaste_2026-04-29_18-29-00.png)

## 技术栈

| 层 | 组件 |
| --- | --- |
| Backend | `FastAPI`、`SQLAlchemy`、`Alembic` |
| Retrieval | `Qdrant`、`BM25`、`RRF`、本地 `reranker` |
| AI | `OpenAI-compatible API`、默认 `Ollama`、`BGE-M3`、`qwen3.5:4b` |
| Parsing | `openpyxl`、`pdfplumber`、`markitdown` |
| Frontend | `React 19`、`Vite`、`TanStack Query`、`React Router`、`Tailwind CSS` |
| Infra | `PostgreSQL`、`Docker Compose` |

## 快速开始

### 1. 环境准备

- Python `3.11`
- `uv`
- Docker / Docker Compose
- Ollama
- Node.js 与 `npm`

### 2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

本地默认链路使用 `Ollama + BGE-M3 + hybrid_rerank`。如果不启用 rerank，可以把 `.env` 中的 `RETRIEVAL_MODE` 改成 `hybrid`、`bm25` 或 `vector`。

### 3. 安装依赖

```powershell
uv sync --extra rerank
npm --prefix frontend install
```

### 4. 启动基础服务

```powershell
docker compose up -d db qdrant
uv run alembic upgrade head
```

### 5. 准备本地模型

如果 Ollama 尚未运行，可以单独开一个终端：

```powershell
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:OLLAMA_NUM_PARALLEL="1"
ollama serve
```

拉取默认模型：

```powershell
ollama pull qwen3.5:4b
ollama pull bge-m3
```

### 6. 启动 rerank-adapter

仅当 `RETRIEVAL_MODE=hybrid_rerank` 时需要，单独开一个终端：

```powershell
uv run python script/run_rerank_adapter.py
```

### 7. 重建向量库并导入文档

```powershell
uv run python script/reset_qdrant_collection.py --collection documents
uv run python script/ingest_repo_spec.py --dir docs --pattern *.xlsx --recursive
```

也可以导入单个文件：

```powershell
uv run python script/ingest_repo_spec.py --file "docs\設計_処理設計書_excel_parser.xlsx"
```

### 8. 创建初始登录用户

先生成 bcrypt 密码哈希：

```powershell
uv run python -c "from app.core.security import hash_password; print(hash_password('123456'))"
```

把输出写入数据库：

```sql
INSERT INTO users (username, hashed_password, role)
VALUES
  ('admin_demo', '<PUT_HASH_HERE>', 'admin'),
  ('manager_demo', '<PUT_HASH_HERE>', 'manager'),
  ('staff_demo', '<PUT_HASH_HERE>', 'staff');
```

### 9. 启动应用

后端：

```powershell
uv run uvicorn app.main:app --reload
```

前端：

```powershell
npm --prefix frontend run dev
```

访问地址：

| 服务 | 地址 |
| --- | --- |
| FastAPI | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| Frontend | `http://127.0.0.1:5173` |
| Login | `http://127.0.0.1:5173/login` |
| Chat | `http://127.0.0.1:5173/chat` |
| Qdrant HTTP | `http://127.0.0.1:6333` |
| rerank-adapter | `http://localhost:8090` |

## API 概览

### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 表单登录，返回 JWT |
| `GET` | `/api/v1/auth/me` | 获取当前用户 |

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

提问示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/rag/ask" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"FN-007 的功能名是什么？\"}"
```

## 文档解析与导入

- `.xlsx` / `.xlsm`：优先使用 `JapaneseExcelParser`
- `.xls` / `.xlsb`：使用 `MarkItDownFallback`
- `.pdf`：优先使用 `PDFMarkdownParser`
- 导入后的 metadata 包含 `source_file`、`source_key`、`allowed_roles`、`chunk_index`、`sheet_name`、`cell_range`、`content_type`

## 目录结构

```text
.
├─ app/                 后端应用
│  ├─ api/v1/           auth / docs / rag / health 接口
│  ├─ core/             配置、鉴权、日志、错误处理
│  ├─ db/               SQLAlchemy 模型与数据库连接
│  ├─ clients/          Qdrant 客户端封装
│  └─ services/         解析、导入、检索、RAG、rerank 等核心逻辑
├─ frontend/            React 前端
├─ script/              导入、评测、Qdrant 重置、rerank 启动脚本
├─ docs/                设计文档、式样书与评测报告
├─ tests/               单元测试与集成测试
├─ alembic/             数据库迁移
├─ docker-compose.yml   PostgreSQL / Qdrant / pgAdmin
└─ .env.example         环境变量示例
```

## 测试

后端测试：

```powershell
uv run pytest
```

前端检查：

```powershell
npm --prefix frontend run lint
```

## License

本项目采用 [`Apache-2.0`](./LICENSE) 许可证。
