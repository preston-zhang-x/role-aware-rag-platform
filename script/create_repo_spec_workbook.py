from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "app" / "api" / "v1"
MODEL_DIR = ROOT_DIR / "app" / "db" / "models"
SERVICE_DIR = ROOT_DIR / "app" / "services"
CORE_DIR = ROOT_DIR / "app" / "core"
CLIENT_DIR = ROOT_DIR / "app" / "clients"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "docs" / "role_aware_rag_platform_spec.xlsx"
FONT_NAME = "Meiryo"

COLOR_TITLE = "1F4E78"
COLOR_SECTION = "D9E2F3"
COLOR_REQUIRED = "FFF2CC"
COLOR_READONLY = "EDEDED"
COLOR_AUTO = "E2F0D9"
COLOR_AUTH = "FCE4D6"
COLOR_FORMULA = "EAF2F8"
COLOR_WHITE = "FFFFFF"
COLOR_ALT = "F8FBFF"
COLOR_NOTE = "F4F8FC"

THIN_SIDE = Side(style="thin", color="808080")
DEFAULT_BORDER = Border(
    left=THIN_SIDE,
    right=THIN_SIDE,
    top=THIN_SIDE,
    bottom=THIN_SIDE,
)

CellValue = str | int | float | bool | None


@dataclass(frozen=True)
class ApiFieldSpec:
    name: str
    type_name: str
    required: bool
    default_text: str
    rule_text: str
    description: str
    location: str


@dataclass(frozen=True)
class PydanticFieldSpec:
    name: str
    type_name: str
    required: bool
    default_text: str
    description: str
    min_length: str
    max_length: str

    @property
    def rule_text(self) -> str:
        rules: list[str] = []
        if self.min_length not in {"", "-"}:
            rules.append(f"min_length={self.min_length}")
        if self.max_length not in {"", "-"}:
            rules.append(f"max_length={self.max_length}")
        return ", ".join(rules) if rules else "-"


@dataclass(frozen=True)
class PydanticModelSpec:
    name: str
    fields: list[PydanticFieldSpec]


@dataclass(frozen=True)
class EndpointErrorSpec:
    status_code: int
    detail: str


@dataclass(frozen=True)
class EndpointSpec:
    if_id: str
    group: str
    function_name: str
    title: str
    feature_id: str
    screen_id: str
    method: str
    path: str
    success_status: int
    auth_text: str
    auth_kind: str
    summary: str
    request_model: str
    response_model: str
    path_params: list[ApiFieldSpec] = field(default_factory=list)
    query_params: list[ApiFieldSpec] = field(default_factory=list)
    form_fields: list[ApiFieldSpec] = field(default_factory=list)
    body_fields: list[ApiFieldSpec] = field(default_factory=list)
    response_fields: list[ApiFieldSpec] = field(default_factory=list)
    errors: list[EndpointErrorSpec] = field(default_factory=list)
    note: str = "-"
    source_file: str = "-"
    line_no: int = 0


@dataclass(frozen=True)
class TableColumnSpec:
    column_id: str
    table_id: str
    table_name: str
    name: str
    type_name: str
    python_type: str
    length_text: str
    nullable: bool
    primary_key: bool
    unique: bool
    default_text: str
    auto_text: str
    description: str
    note: str


@dataclass(frozen=True)
class TableSpec:
    table_id: str
    name: str
    source_file: str
    summary: str
    columns: list[TableColumnSpec]


@dataclass(frozen=True)
class SettingSpec:
    setting_id: str
    module_path: str
    class_name: str
    field_name: str
    env_name: str
    type_name: str
    required: bool
    code_default: str
    example_value: str
    description: str
    note: str


@dataclass(frozen=True)
class VectorMetadataSpec:
    name: str
    type_name: str
    description: str
    required: bool
    source: str


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    name: str
    category: str
    summary: str
    auth_text: str
    related_if_ids: str
    screen_id: str
    source: str
    note: str


@dataclass(frozen=True)
class ScreenSpec:
    screen_id: str
    name: str
    summary: str
    auth_text: str
    related_if_ids: str
    note: str


@dataclass(frozen=True)
class ScreenItemSpec:
    item_id: str
    screen_id: str
    screen_name: str
    item_name: str
    ui_type: str
    type_name: str
    length_text: str
    required_text: str
    default_text: str
    rule_text: str
    active_condition: str
    editable_text: str
    auto_text: str
    error_message: str
    related_if: str
    related_column: str
    note: str


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    category: str
    condition: str
    when_text: str
    then_text: str
    source: str
    related_if: str
    note: str


@dataclass(frozen=True)
class ErrorSpec:
    error_id: str
    category: str
    source: str
    status_text: str
    message: str
    trigger: str
    recovery: str
    note: str


@dataclass(frozen=True)
class TestPointSpec:
    test_id: str
    area: str
    source_file: str
    scenario: str
    expected: str
    related_if: str
    related_rule: str
    note: str


@dataclass(frozen=True)
class RepoSpecBundle:
    endpoints: list[EndpointSpec]
    tables: list[TableSpec]
    settings: list[SettingSpec]
    features: list[FeatureSpec]
    screens: list[ScreenSpec]
    screen_items: list[ScreenItemSpec]
    rules: list[RuleSpec]
    errors: list[ErrorSpec]
    test_points: list[TestPointSpec]
    parser_warnings: list[tuple[str, str]]
    supported_extensions: list[str]
    vector_collection_name: str
    vector_top_k: str
    chunk_size: str
    chunk_overlap: str
    batch_size: str
    embedding_model: str
    embedding_dimensions: str
    chat_model: str
    vector_metadata: list[VectorMetadataSpec]


ENDPOINT_CATALOG: dict[str, dict[str, str]] = {
    "Auth:login": {
        "if_id": "IF-001",
        "title": "ログイン",
        "feature_id": "FN-001",
        "screen_id": "SCR-001",
        "summary": "ユーザー名とパスワードを受け取り、JWT を発行する。",
        "note": "OAuth2PasswordRequestForm を使用する。",
    },
    "Auth:read_me": {
        "if_id": "IF-002",
        "title": "自分情報取得",
        "feature_id": "FN-002",
        "screen_id": "SCR-001",
        "summary": "現在ログイン中のユーザー名とロールを返す。",
        "note": "Bearer トークン必須。",
    },
    "Docs:create_doc": {
        "if_id": "IF-003",
        "title": "文書登録",
        "feature_id": "FN-003",
        "screen_id": "SCR-002",
        "summary": "タイトルと本文から文書を登録する。",
        "note": "admin / editor のみ実行可能。",
    },
    "Docs:list_docs": {
        "if_id": "IF-004",
        "title": "文書一覧取得",
        "feature_id": "FN-004",
        "screen_id": "SCR-002",
        "summary": "ページング付きで文書一覧を返す。",
        "note": "skip / limit の境界条件あり。",
    },
    "Docs:get_doc": {
        "if_id": "IF-005",
        "title": "文書詳細取得",
        "feature_id": "FN-005",
        "screen_id": "SCR-002",
        "summary": "文書 ID 指定で 1 件取得する。",
        "note": "存在しない ID は 404。",
    },
    "Docs:update_doc": {
        "if_id": "IF-006",
        "title": "文書更新",
        "feature_id": "FN-006",
        "screen_id": "SCR-002",
        "summary": "タイトルまたは本文を更新する。",
        "note": "admin / editor のみ実行可能。",
    },
    "Docs:delete_doc": {
        "if_id": "IF-007",
        "title": "文書削除",
        "feature_id": "FN-007",
        "screen_id": "SCR-002",
        "summary": "文書 ID 指定で文書を削除する。",
        "note": "admin のみ実行可能。",
    },
    "RAG:ask": {
        "if_id": "IF-008",
        "title": "RAG 問合せ",
        "feature_id": "FN-008",
        "screen_id": "SCR-003",
        "summary": "質問文を埋め込み検索し、回答と出典チャンクを返す。",
        "note": "現状実装では JWT ではなく request body の role でフィルタする。",
    },
    "Health:liveness": {
        "if_id": "IF-009",
        "title": "Live チェック",
        "feature_id": "FN-012",
        "screen_id": "SCR-004",
        "summary": "アプリ生存確認用の軽量エンドポイント。",
        "note": "依存先確認は行わない。",
    },
    "Health:readiness": {
        "if_id": "IF-010",
        "title": "Ready チェック",
        "feature_id": "FN-012",
        "screen_id": "SCR-004",
        "summary": "DB と Qdrant の依存状態を確認する。",
        "note": "異常時は 503 degraded を返す。",
    },
    "Health:health": {
        "if_id": "IF-011",
        "title": "Health エイリアス",
        "feature_id": "FN-012",
        "screen_id": "SCR-004",
        "summary": "Ready チェックをそのまま公開する別パス。",
        "note": "実装上は readiness() を呼び出す。",
    },
}

SETTING_DESCRIPTIONS: dict[tuple[str, str], tuple[str, str]] = {
    ("SecuritySettings", "secret_key"): ("JWT 署名鍵。", "実運用値は `.env` に保持し、仕様書では開示しない。"),
    ("SecuritySettings", "algorithm"): ("JWT 署名アルゴリズム。", "既定値は HS256。"),
    ("SecuritySettings", "access_token_expire_minutes"): ("アクセストークン有効期限。", "分単位。"),
    ("OpenAISettings", "openai_api_key"): ("OpenAI API キー。", "任意扱いだが外部 API 利用時は実質必須。"),
    ("OpenAISettings", "openai_base_url"): ("OpenAI 互換 API のベース URL。", "既定の `.env.example` は OpenAI 公式 URL。"),
    ("OpenAISettings", "embedding_model"): ("埋め込みモデル名。", "Ingest / Query の両方で使用。"),
    ("OpenAISettings", "embedding_dimensions"): ("埋め込み次元数。", "Qdrant の vector size と整合が必要。"),
    ("OpenAISettings", "chat_model"): ("回答生成用の Chat モデル。", "既定値は gpt-4o-mini。"),
    ("QdrantSettings", "qdrant_url"): ("Qdrant 接続 URL。", "ローカルまたはクラウド接続先。"),
    ("QdrantSettings", "qdrant_api_key"): ("Qdrant API キー。", "ローカル開発時は空欄可。"),
    ("DBSettings", "database_url"): ("SQLAlchemy 接続文字列。", "未設定時はアプリ起動不可。"),
}


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_module(path: Path) -> ast.Module:
    return ast.parse(_read_source(path))


def _expr_text(node: ast.AST | None) -> str:
    if node is None:
        return "-"
    return ast.unparse(node)


def _simple_value(node: ast.AST | None) -> Any:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_simple_value(item) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_simple_value(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        result: dict[Any, Any] = {}
        for key, value in zip(node.keys, node.values):
            result[_simple_value(key)] = _simple_value(value)
        return result
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -1 * _simple_value(node.operand)
    return _expr_text(node)


def _display_value(node: ast.AST | None) -> str:
    value = _simple_value(node)
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return str(value)


def _extract_name(expr: ast.AST | None) -> str:
    if expr is None:
        return ""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return _expr_text(expr)


def _status_code_from_expr(node: ast.AST | None, default: int = 200) -> int:
    if node is None:
        return default
    value = _simple_value(node)
    if isinstance(value, int):
        return value
    status_map = {
        "status.HTTP_201_CREATED": 201,
        "status.HTTP_204_NO_CONTENT": 204,
        "status.HTTP_401_UNAUTHORIZED": 401,
        "status.HTTP_403_FORBIDDEN": 403,
        "http_status.HTTP_401_UNAUTHORIZED": 401,
        "http_status.HTTP_403_FORBIDDEN": 403,
    }
    return status_map.get(_expr_text(node), default)


def _status_text(code: int) -> str:
    labels = {
        200: "200 OK",
        201: "201 Created",
        204: "204 No Content",
        401: "401 Unauthorized",
        403: "403 Forbidden",
        404: "404 Not Found",
        500: "500 Internal Server Error",
        503: "503 Service Unavailable",
    }
    return labels.get(code, str(code))


def _field_keyword(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _normalize_route_path(prefix: str, route_path: str) -> str:
    if route_path == "":
        return prefix
    if prefix.endswith("/") and route_path.startswith("/"):
        return prefix[:-1] + route_path
    if not prefix.endswith("/") and not route_path.startswith("/"):
        return prefix + "/" + route_path
    return prefix + route_path


def _field_rule_parts(call: ast.Call) -> tuple[str, str]:
    return _display_value(_field_keyword(call, "min_length")), _display_value(_field_keyword(call, "max_length"))


def _parse_pydantic_field(annotation: ast.AST, value: ast.AST | None) -> PydanticFieldSpec:
    type_name = _expr_text(annotation)
    required = value is None
    default_text = "-"
    description = "-"
    min_length = "-"
    max_length = "-"
    if isinstance(value, ast.Call) and _extract_name(value.func) == "Field":
        default_node = _field_keyword(value, "default")
        if default_node is None and value.args:
            default_node = value.args[0]
        if default_node is not None:
            default_text = _display_value(default_node)
            required = default_text in {"Ellipsis", "..."}
        description = _display_value(_field_keyword(value, "description"))
        min_length, max_length = _field_rule_parts(value)
    elif value is not None:
        default_text = _display_value(value)
        required = False
    if default_text in {"Ellipsis", "..."}:
        default_text = "-"
    return PydanticFieldSpec("", type_name, required, default_text, description, min_length, max_length)


def _extract_pydantic_models(module: ast.Module) -> dict[str, PydanticModelSpec]:
    raw_fields: dict[str, list[PydanticFieldSpec]] = {}
    bases: dict[str, list[str]] = {}
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = [_extract_name(base) for base in node.bases]
        if "BaseModel" not in base_names and not any(base in raw_fields for base in base_names):
            continue
        bases[node.name] = base_names
        fields: list[PydanticFieldSpec] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                parsed = _parse_pydantic_field(item.annotation, item.value)
                fields.append(
                    PydanticFieldSpec(
                        item.target.id,
                        parsed.type_name,
                        parsed.required,
                        parsed.default_text,
                        parsed.description,
                        parsed.min_length,
                        parsed.max_length,
                    )
                )
        raw_fields[node.name] = fields

    resolved: dict[str, PydanticModelSpec] = {}

    def resolve(name: str) -> PydanticModelSpec:
        if name in resolved:
            return resolved[name]
        merged: dict[str, PydanticFieldSpec] = {}
        for base_name in bases.get(name, []):
            if base_name in raw_fields:
                for field_spec in resolve(base_name).fields:
                    merged[field_spec.name] = field_spec
        for field_spec in raw_fields.get(name, []):
            merged[field_spec.name] = field_spec
        resolved[name] = PydanticModelSpec(name, list(merged.values()))
        return resolved[name]

    for model_name in raw_fields:
        resolve(model_name)
    return resolved


def _resolve_model_name(model_text: str) -> str:
    text = model_text.strip()
    return text[5:-1] if text.startswith("list[") and text.endswith("]") else text


def _extract_router_prefix(module: ast.Module) -> str:
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != "router" or not isinstance(node.value, ast.Call):
            continue
        if _extract_name(node.value.func) != "APIRouter":
            continue
        prefix = _field_keyword(node.value, "prefix")
        return _display_value(prefix)
    return ""


def _query_field_from_arg(arg: ast.arg, query_call: ast.Call) -> ApiFieldSpec:
    rules: list[str] = []
    ge = _display_value(_field_keyword(query_call, "ge"))
    le = _display_value(_field_keyword(query_call, "le"))
    if ge not in {"", "-"}:
        rules.append(f"ge={ge}")
    if le not in {"", "-"}:
        rules.append(f"le={le}")
    default_value = _display_value(_field_keyword(query_call, "default"))
    return ApiFieldSpec(arg.arg, _expr_text(arg.annotation), default_value == "-", default_value, ", ".join(rules) if rules else "-", "-", "query")


def _body_fields_from_model(model_text: str, models: dict[str, PydanticModelSpec], location: str) -> list[ApiFieldSpec]:
    model = models.get(_resolve_model_name(model_text))
    if not model:
        return []
    return [
        ApiFieldSpec(field_spec.name, field_spec.type_name, field_spec.required, field_spec.default_text, field_spec.rule_text, field_spec.description, location)
        for field_spec in model.fields
    ]


def _path_params_from_signature(function_node: ast.FunctionDef, path: str) -> list[ApiFieldSpec]:
    placeholders = set(re.findall(r"{([^}]+)}", path))
    defaults = [None] * (len(function_node.args.args) - len(function_node.args.defaults)) + list(function_node.args.defaults)
    params: list[ApiFieldSpec] = []
    for arg, default in zip(function_node.args.args, defaults):
        if arg.arg not in placeholders:
            continue
        if isinstance(default, ast.Call) and _extract_name(default.func) in {"Depends", "Query"}:
            continue
        params.append(ApiFieldSpec(arg.arg, _expr_text(arg.annotation), True, "-", "Path パラメータ", "-", "path"))
    return params


def _dependency_text(default_node: ast.AST | None) -> str:
    if isinstance(default_node, ast.Call) and _extract_name(default_node.func) == "Depends":
        return _expr_text(default_node.args[0]) if default_node.args else "Depends()"
    return ""


def _derive_auth(function_node: ast.FunctionDef, decorator: ast.Call) -> tuple[str, str]:
    dependency_texts: list[str] = []
    defaults = [None] * (len(function_node.args.args) - len(function_node.args.defaults)) + list(function_node.args.defaults)
    for default_node in defaults:
        text = _dependency_text(default_node)
        if text:
            dependency_texts.append(text)
    decorator_dependencies = _field_keyword(decorator, "dependencies")
    if isinstance(decorator_dependencies, ast.List):
        dependency_texts.extend(_expr_text(item) for item in decorator_dependencies.elts)

    role_names: list[str] = []
    for text in dependency_texts:
        if "require_roles" in text:
            role_names.extend(match.lower() for match in re.findall(r"UserRole\.([A-Z_]+)", text))
    if role_names:
        unique_roles = list(dict.fromkeys(role_names))
        return f"Bearer 必須 / {', '.join(unique_roles)}", "role"
    if any("get_current_user" in text for text in dependency_texts):
        return "Bearer 必須 / 認証済み", "bearer"
    return "不要", "open"


def _extract_http_exceptions(function_node: ast.FunctionDef) -> list[EndpointErrorSpec]:
    errors: list[EndpointErrorSpec] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if _extract_name(node.exc.func) != "HTTPException":
            continue
        status_code = 500
        detail = "-"
        for keyword in node.exc.keywords:
            if keyword.arg == "status_code":
                status_code = _status_code_from_expr(keyword.value, 500)
            if keyword.arg == "detail":
                detail = _display_value(keyword.value)
        key = (status_code, detail)
        if key not in seen:
            errors.append(EndpointErrorSpec(status_code, detail))
            seen.add(key)
    return errors


def _build_form_fields_for_login() -> list[ApiFieldSpec]:
    return [
        ApiFieldSpec("username", "str", True, "-", "OAuth2 Password form", "ログイン ID", "form"),
        ApiFieldSpec("password", "str", True, "-", "OAuth2 Password form", "平文パスワード", "form"),
    ]


def _add_common_endpoint_errors(endpoint: EndpointSpec) -> EndpointSpec:
    errors = list(endpoint.errors)
    seen = {(item.status_code, item.detail) for item in errors}

    def add(status_code: int, detail: str) -> None:
        key = (status_code, detail)
        if key not in seen:
            errors.append(EndpointErrorSpec(status_code, detail))
            seen.add(key)

    if endpoint.auth_kind in {"bearer", "role"}:
        add(401, "Could not validate credentials")
        add(401, "User not found")
    if endpoint.auth_kind == "role":
        add(403, "Not enough permissions")
    if endpoint.if_id in {"IF-010", "IF-011"}:
        add(503, '{"status":"degraded","checks":...}')
    return EndpointSpec(
        endpoint.if_id,
        endpoint.group,
        endpoint.function_name,
        endpoint.title,
        endpoint.feature_id,
        endpoint.screen_id,
        endpoint.method,
        endpoint.path,
        endpoint.success_status,
        endpoint.auth_text,
        endpoint.auth_kind,
        endpoint.summary,
        endpoint.request_model,
        endpoint.response_model,
        endpoint.path_params,
        endpoint.query_params,
        endpoint.form_fields,
        endpoint.body_fields,
        endpoint.response_fields,
        errors,
        endpoint.note,
        endpoint.source_file,
        endpoint.line_no,
    )


def extract_endpoints() -> list[EndpointSpec]:
    endpoints: list[EndpointSpec] = []
    for filename, group in [("auth.py", "Auth"), ("docs.py", "Docs"), ("rag.py", "RAG"), ("health.py", "Health")]:
        path = API_DIR / filename
        module = _read_module(path)
        prefix = _extract_router_prefix(module)
        models = _extract_pydantic_models(module)
        for node in module.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            route_decorator: ast.Call | None = None
            method = ""
            route_path = ""
            response_model = "-"
            status_code = 200
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if _extract_name(decorator.func.value) != "router":
                    continue
                route_decorator = decorator
                method = decorator.func.attr.upper()
                route_path = _display_value(decorator.args[0]) if decorator.args else ""
                response_model = _display_value(_field_keyword(decorator, "response_model"))
                status_code = _status_code_from_expr(_field_keyword(decorator, "status_code"), 200)
                break
            if route_decorator is None:
                continue

            path_text = _normalize_route_path(prefix, route_path)
            catalog = ENDPOINT_CATALOG[f"{group}:{node.name}"]
            auth_text, auth_kind = _derive_auth(node, route_decorator)
            defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults)
            query_params: list[ApiFieldSpec] = []
            form_fields: list[ApiFieldSpec] = []
            body_fields: list[ApiFieldSpec] = []
            request_model = "-"
            for arg, default in zip(node.args.args, defaults):
                annotation_text = _expr_text(arg.annotation)
                if annotation_text in models and not _dependency_text(default):
                    request_model = annotation_text
                    body_fields = _body_fields_from_model(annotation_text, models, "body")
                    continue
                if isinstance(default, ast.Call) and _extract_name(default.func) == "Query":
                    query_params.append(_query_field_from_arg(arg, default))
                    continue
                if annotation_text == "OAuth2PasswordRequestForm":
                    request_model = "OAuth2PasswordRequestForm"
                    form_fields = _build_form_fields_for_login()
            endpoint = EndpointSpec(
                catalog["if_id"],
                group,
                node.name,
                catalog["title"],
                catalog["feature_id"],
                catalog["screen_id"],
                method,
                path_text,
                status_code,
                auth_text,
                auth_kind,
                catalog["summary"],
                request_model,
                response_model,
                _path_params_from_signature(node, path_text),
                query_params,
                form_fields,
                body_fields,
                _body_fields_from_model(response_model, models, "response"),
                _extract_http_exceptions(node),
                catalog["note"],
                str(path.relative_to(ROOT_DIR)),
                node.lineno,
            )
            endpoints.append(_add_common_endpoint_errors(endpoint))
    endpoints.sort(key=lambda item: item.if_id)
    return endpoints


def _extract_enum_values(path: Path, class_name: str) -> list[str]:
    module = _read_module(path)
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values: list[str] = []
            for item in node.body:
                if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                    values.append(str(_simple_value(item.value)))
            return values
    return []


def _annotation_inner_type(annotation: ast.AST) -> str:
    if isinstance(annotation, ast.Subscript) and _extract_name(annotation.value) == "Mapped":
        return _expr_text(annotation.slice)
    return _expr_text(annotation)


def _render_column_type(call: ast.Call, python_type: str, enum_values: list[str]) -> tuple[str, str]:
    if call.args:
        first = call.args[0]
        func_name = _extract_name(first.func) if isinstance(first, ast.Call) else _extract_name(first)
        if isinstance(first, ast.Call) and func_name == "String":
            length = _display_value(first.args[0] if first.args else None)
            return f"VARCHAR({length})", length
        if func_name == "Text":
            return "TEXT", "-"
        if isinstance(first, ast.Call) and func_name == "DateTime":
            return "TIMESTAMP", "-"
        if isinstance(first, ast.Call) and func_name == "SqlEnum":
            joined = "/".join(enum_values) if enum_values else "enum"
            return f"ENUM({joined})", "-"
    defaults = {
        "int": ("INTEGER", "-"),
        "str": ("VARCHAR", "-"),
        "datetime": ("TIMESTAMP", "-"),
        "UserRole": (f"ENUM({'/'.join(enum_values)})" if enum_values else "ENUM", "-"),
    }
    return defaults.get(python_type, (python_type, "-"))


def _extract_mapped_column_keywords(call: ast.Call) -> dict[str, str]:
    return {
        keyword.arg: _display_value(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }


def extract_tables() -> list[TableSpec]:
    enum_values = _extract_enum_values(MODEL_DIR / "user.py", "UserRole")
    table_catalog = {
        "User": ("TBL-001", "users", "認証ユーザーとロールを保持する。"),
        "Document": ("TBL-002", "documents", "文書 CRUD の永続化テーブル。"),
    }
    column_counts = {"TBL-001": 1, "TBL-002": 1}
    tables: list[TableSpec] = []
    for filename in ["user.py", "document.py"]:
        path = MODEL_DIR / filename
        module = _read_module(path)
        for node in module.body:
            if not isinstance(node, ast.ClassDef) or "Base" not in [_extract_name(base) for base in node.bases]:
                continue
            table_id, table_name, summary = table_catalog[node.name]
            columns: list[TableColumnSpec] = []
            for item in node.body:
                if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                    continue
                if not isinstance(item.value, ast.Call) or _extract_name(item.value.func) != "mapped_column":
                    continue
                python_type = _annotation_inner_type(item.annotation)
                rendered_type, length_text = _render_column_type(item.value, python_type, enum_values)
                keywords = _extract_mapped_column_keywords(item.value)
                primary_key = keywords.get("primary_key", "False") == "True"
                unique = keywords.get("unique", "False") == "True"
                nullable = False if primary_key else keywords.get("nullable", "True") == "True"
                default_parts: list[str] = []
                if "default" in keywords:
                    default_parts.append(keywords["default"].replace("UserRole.", "").lower())
                if "server_default" in keywords:
                    default_parts.append(keywords["server_default"])
                default_text = " / ".join(default_parts) if default_parts else "-"
                auto_parts: list[str] = []
                if primary_key:
                    auto_parts.append("PK")
                if "server_default" in keywords:
                    auto_parts.append("server_default")
                if "onupdate" in keywords:
                    auto_parts.append("onupdate")
                description = "-"
                note = "-"
                if table_name == "users":
                    description_map = {
                        "id": "ユーザーID",
                        "username": "ログイン名",
                        "hashed_password": "ハッシュ化済みパスワード",
                        "role": "ユーザーロール",
                    }
                    description = description_map.get(item.target.id, "-")
                if table_name == "documents":
                    description_map = {
                        "id": "文書ID",
                        "title": "文書タイトル",
                        "content": "文書本文",
                        "created_at": "作成日時",
                        "updated_at": "更新日時",
                    }
                    description = description_map.get(item.target.id, "-")
                if table_name == "users" and item.target.id == "role":
                    note = "実装値は admin/editor/viewer。migration には大文字 enum 字面が残る。"
                column_id = f"COL-{table_id}-{column_counts[table_id]:03d}"
                column_counts[table_id] += 1
                columns.append(
                    TableColumnSpec(
                        column_id,
                        table_id,
                        table_name,
                        item.target.id,
                        rendered_type,
                        python_type,
                        length_text,
                        nullable,
                        primary_key,
                        unique,
                        default_text,
                        ", ".join(auto_parts) if auto_parts else "-",
                        description,
                        note,
                    )
                )
            tables.append(TableSpec(table_id, table_name, str(path.relative_to(ROOT_DIR)), summary, columns))
    tables.sort(key=lambda item: item.table_id)
    return tables


def _parse_env_example() -> dict[str, str]:
    env_map: dict[str, str] = {}
    for raw_line in _read_source(ROOT_DIR / ".env.example").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key] = value
    return env_map


def extract_settings() -> list[SettingSpec]:
    env_map = _parse_env_example()
    files = [CORE_DIR / "config.py", CLIENT_DIR / "qdrant_client.py", ROOT_DIR / "app" / "db" / "session.py"]
    id_counter = 1
    settings: list[SettingSpec] = []
    for path in files:
        module = _read_module(path)
        for node in module.body:
            if not isinstance(node, ast.ClassDef) or "BaseSettings" not in [_extract_name(base) for base in node.bases]:
                continue
            for item in node.body:
                if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                    continue
                env_name = item.target.id.upper()
                explicit_env = {
                    "openai_api_key": "OPENAI_API_KEY",
                    "openai_base_url": "OPENAI_BASE_URL",
                    "embedding_model": "EMBEDDING_MODEL",
                    "embedding_dimensions": "EMBEDDING_DIMENSIONS",
                    "chat_model": "CHAT_MODEL",
                    "database_url": "DATABASE_URL",
                }
                env_name = explicit_env.get(item.target.id, env_name)
                description, note = SETTING_DESCRIPTIONS.get((node.name, item.target.id), ("-", "-"))
                settings.append(
                    SettingSpec(
                        f"CFG-{id_counter:03d}",
                        str(path.relative_to(ROOT_DIR)),
                        node.name,
                        item.target.id,
                        env_name,
                        _expr_text(item.annotation),
                        item.value is None,
                        _display_value(item.value),
                        env_map.get(env_name, ""),
                        description,
                        note,
                    )
                )
                id_counter += 1
    return settings


def _extract_parser_warning_values() -> list[tuple[str, str]]:
    module = _read_module(SERVICE_DIR / "parse_result.py")
    warnings: list[tuple[str, str]] = []
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ParserWarning":
            continue
        for item in node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                warnings.append((item.targets[0].id, _display_value(item.value)))
    return warnings


def _extract_document_loader_extensions() -> list[str]:
    module = _read_module(SERVICE_DIR / "document_loader.py")
    for node in ast.walk(module):
        if isinstance(node, ast.Dict):
            keys = [_simple_value(key) for key in node.keys]
            if keys and all(isinstance(key, str) and key.startswith(".") for key in keys):
                return sorted(str(key) for key in keys)
    return []


def _extract_service_constants() -> dict[str, str]:
    targets = {
        SERVICE_DIR / "ingest_service.py": {"DEFAULT_COLLECTION", "CHUNK_SIZE", "CHUNK_OVERLAP", "BATCH_SIZE"},
        SERVICE_DIR / "rag_service.py": {"DEFAULT_COLLECTION", "DEFAULT_TOP_K"},
    }
    values: dict[str, str] = {}
    for path, names in targets.items():
        module = _read_module(path)
        for node in module.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in names:
                    values[node.targets[0].id] = _display_value(node.value)
    return values


def _extract_vector_metadata() -> list[VectorMetadataSpec]:
    descriptions = {
        "source_file": "元ファイルパス。出典表示に使う。",
        "source_key": "絶対パス由来の安定キー。再取込時削除にも使う。",
        "allowed_roles": "検索時のロールフィルタ対象。",
        "chunk_index": "ファイル内のチャンク順序。",
        "formula_description": "Excel 関数検出時に補足説明として付与。",
    }
    module = _read_module(SERVICE_DIR / "ingest_service.py")
    items: list[VectorMetadataSpec] = []
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != "IngestService":
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name != "_build_metadata":
                continue
            for child in ast.walk(item):
                if isinstance(child, ast.Dict):
                    keys = [_simple_value(key) for key in child.keys]
                    if "source_file" not in keys:
                        continue
                    for key in keys:
                        if not isinstance(key, str):
                            continue
                        items.append(
                            VectorMetadataSpec(
                                key,
                                "list[str]" if key == "allowed_roles" else ("int" if key == "chunk_index" else "str"),
                                descriptions.get(key, "-"),
                                key != "formula_description",
                                "app/services/ingest_service.py::_build_metadata",
                            )
                        )
    unique: list[VectorMetadataSpec] = []
    seen: set[str] = set()
    for item in items:
        if item.name not in seen:
            unique.append(item)
            seen.add(item.name)
    if "formula_description" not in seen:
        unique.append(
            VectorMetadataSpec(
                "formula_description",
                "str",
                descriptions["formula_description"],
                False,
                "app/services/ingest_service.py::_build_metadata",
            )
        )
    return unique


def build_features(endpoints: Sequence[EndpointSpec]) -> list[FeatureSpec]:
    endpoint_map = {endpoint.if_id: endpoint for endpoint in endpoints}
    return [
        FeatureSpec("FN-001", "ログイン / JWT 発行", "認証", "ログイン資格情報を検証しアクセストークンを返す。", endpoint_map["IF-001"].auth_text, "IF-001", "SCR-001", "app/api/v1/auth.py", "JWT には role ではなく subject を格納する。"),
        FeatureSpec("FN-002", "自分情報参照", "認証", "トークンから現ユーザーを解決して username / role を返す。", endpoint_map["IF-002"].auth_text, "IF-002", "SCR-001", "app/api/v1/auth.py", "User 未解決時は 401。"),
        FeatureSpec("FN-003", "文書登録", "文書管理", "タイトルと本文から文書を新規登録する。", endpoint_map["IF-003"].auth_text, "IF-003", "SCR-002", "app/api/v1/docs.py", "admin/editor のみ。"),
        FeatureSpec("FN-004", "文書一覧取得", "文書管理", "skip / limit 付きで文書一覧を取得する。", endpoint_map["IF-004"].auth_text, "IF-004", "SCR-002", "app/api/v1/docs.py", "limit 上限は 100。"),
        FeatureSpec("FN-005", "文書詳細取得", "文書管理", "文書 ID 指定で 1 件取得する。", endpoint_map["IF-005"].auth_text, "IF-005", "SCR-002", "app/api/v1/docs.py", "存在しない文書は 404。"),
        FeatureSpec("FN-006", "文書更新", "文書管理", "タイトルと本文を部分更新する。", endpoint_map["IF-006"].auth_text, "IF-006", "SCR-002", "app/api/v1/docs.py", "未指定項目は更新しない。"),
        FeatureSpec("FN-007", "文書削除", "文書管理", "文書 ID 指定で物理削除する。", endpoint_map["IF-007"].auth_text, "IF-007", "SCR-002", "app/api/v1/docs.py", "admin のみ。"),
        FeatureSpec("FN-008", "RAG 問合せ", "検索 / 回答", "質問を埋め込み検索し、回答と出典チャンクを返す。", endpoint_map["IF-008"].auth_text, "IF-008", "SCR-003", "app/api/v1/rag.py", "現状は body.role によるロール制御。"),
        FeatureSpec("FN-009", "文書取込 / ベクトル化", "Ingest", "DocumentLoader -> split -> embedding -> Qdrant 保存まで行う。", "内部機能", "-", "-", "app/services/ingest_service.py", "再取込時は source_file/source_key で既存ポイントを削除。"),
        FeatureSpec("FN-010", "Excel 仕様書解析", "Parser", "結合セル展開と密度判定で日本式 Excel を Markdown 化する。", "内部機能", "-", "-", "app/services/excel_parser.py", "Hidden sheet は warning を出してスキップ。"),
        FeatureSpec("FN-011", "PDF 解析", "Parser", "テキストと表を抽出し Markdown に整形する。", "内部機能", "-", "-", "app/services/pdf_parser.py", "スキャンページは warning を出す。"),
        FeatureSpec("FN-012", "ヘルス監視", "運用", "liveness / readiness でアプリと依存先の状態を返す。", endpoint_map["IF-010"].auth_text, "IF-009, IF-010, IF-011", "SCR-004", "app/api/v1/health.py", "degraded 時は 503。"),
    ]


def build_screens() -> list[ScreenSpec]:
    return [
        ScreenSpec("SCR-001", "ログイン / 自分情報画面", "ログイン入力と認証後の自分情報確認を行う推定 UI。", "公開 + Bearer 後", "IF-001, IF-002", "推定UI。現行リポジトリにフロント実装はない。"),
        ScreenSpec("SCR-002", "文書管理画面", "文書一覧・詳細・作成・更新・削除を行う推定 UI。", "Bearer 必須", "IF-003, IF-004, IF-005, IF-006, IF-007", "推定UI。"),
        ScreenSpec("SCR-003", "RAG 問合せ画面", "質問文と role を入力して回答とソースを表示する推定 UI。", "現状は公開", "IF-008", "推定UI。JWT 未接続の現状を反映。"),
        ScreenSpec("SCR-004", "ヘルス監視画面", "live / ready と依存先状態を確認する運用 UI。", "公開", "IF-009, IF-010, IF-011", "推定UI。"),
    ]


def build_screen_items() -> list[ScreenItemSpec]:
    return [
        ScreenItemSpec("ITM-SCR001-001", "SCR-001", "ログイン / 自分情報画面", "username", "text", "str", "50", "Y", "-", "英数字を想定", "未ログイン時", "編集可", "-", "Incorrect username or password", "IF-001", "users.username", "OAuth2 form フィールド"),
        ScreenItemSpec("ITM-SCR001-002", "SCR-001", "ログイン / 自分情報画面", "password", "password", "str", "200", "Y", "-", "平文入力、送信後は保持しない", "未ログイン時", "編集可", "-", "Incorrect username or password", "IF-001", "users.hashed_password", "画面では平文入力"),
        ScreenItemSpec("ITM-SCR001-003", "SCR-001", "ログイン / 自分情報画面", "login button", "button", "-", "-", "N", "-", "クリックで IF-001 実行", "未ログイン時", "編集可", "-", "-", "IF-001", "-", "Enter キー送信を想定"),
        ScreenItemSpec("ITM-SCR001-004", "SCR-001", "ログイン / 自分情報画面", "current user card", "card", "Token/UserMe", "-", "N", "-", "ログイン成功後に IF-002 表示", "ログイン後", "読取専用", "自動取得", "Could not validate credentials", "IF-002", "users.username / users.role", "username / role を表示"),
        ScreenItemSpec("ITM-SCR002-001", "SCR-002", "文書管理画面", "skip", "number", "int", "-", "N", "0", "0 以上", "一覧取得時", "編集可", "-", "-", "IF-004", "-", "ページ先頭位置"),
        ScreenItemSpec("ITM-SCR002-002", "SCR-002", "文書管理画面", "limit", "number", "int", "-", "N", "10", "1-100", "一覧取得時", "編集可", "-", "-", "IF-004", "-", "ページサイズ"),
        ScreenItemSpec("ITM-SCR002-003", "SCR-002", "文書管理画面", "title", "text", "str", "200", "Y", "-", "1-200 文字", "登録/更新時", "編集可", "-", "Document not found", "IF-003, IF-006", "documents.title", "必須入力"),
        ScreenItemSpec("ITM-SCR002-004", "SCR-002", "文書管理画面", "content", "textarea", "str", "n/a", "Y", "-", "1 文字以上", "登録/更新時", "編集可", "-", "Document not found", "IF-003, IF-006", "documents.content", "複数行本文"),
        ScreenItemSpec("ITM-SCR002-005", "SCR-002", "文書管理画面", "document list", "table", "list[DocOut]", "-", "N", "-", "IF-004 応答を表示", "一覧取得後", "読取専用", "自動取得", "Could not validate credentials", "IF-004", "documents.*", "id/title/created_at/updated_at"),
        ScreenItemSpec("ITM-SCR002-006", "SCR-002", "文書管理画面", "delete button", "button", "-", "-", "N", "-", "admin のみ活性", "詳細表示後", "条件付可", "-", "Not enough permissions", "IF-007", "documents.id", "admin 専用"),
        ScreenItemSpec("ITM-SCR003-001", "SCR-003", "RAG 問合せ画面", "question", "textarea", "str", "2000", "Y", "-", "1-2000 文字", "常時", "編集可", "-", "RAG パイプラインでエラーが発生しました", "IF-008", "-", "質問本文"),
        ScreenItemSpec("ITM-SCR003-002", "SCR-003", "RAG 問合せ画面", "role", "select", "str", "-", "N", "viewer", "admin/editor/viewer", "常時", "編集可", "-", "-", "IF-008", "vector.allowed_roles", "現状は body パラメータ"),
        ScreenItemSpec("ITM-SCR003-003", "SCR-003", "RAG 問合せ画面", "answer", "textarea", "str", "-", "N", "-", "応答結果を表示", "問合せ成功後", "読取専用", "自動取得", "-", "IF-008", "-", "生成回答"),
        ScreenItemSpec("ITM-SCR003-004", "SCR-003", "RAG 問合せ画面", "sources", "table", "list[SourceOut]", "-", "N", "-", "text/source_file/score/chunk_index を表示", "問合せ成功後", "読取専用", "自動取得", "-", "IF-008", "vector payload", "出典チャンク一覧"),
        ScreenItemSpec("ITM-SCR004-001", "SCR-004", "ヘルス監視画面", "live status", "card", "dict", "-", "N", "-", "IF-009 の status を表示", "常時", "読取専用", "自動取得", "-", "IF-009", "-", "ok のみ"),
        ScreenItemSpec("ITM-SCR004-002", "SCR-004", "ヘルス監視画面", "ready status", "card", "dict", "-", "N", "-", "IF-010 / IF-011 の overall status を表示", "常時", "読取専用", "自動取得", "-", "IF-010, IF-011", "-", "ok / degraded"),
        ScreenItemSpec("ITM-SCR004-003", "SCR-004", "ヘルス監視画面", "database check", "badge", "str", "-", "N", "-", "checks.database を表示", "ready 実行後", "読取専用", "自動取得", "-", "IF-010, IF-011", "-", "依存先結果"),
        ScreenItemSpec("ITM-SCR004-004", "SCR-004", "ヘルス監視画面", "qdrant check", "badge", "str", "-", "N", "-", "checks.qdrant を表示", "ready 実行後", "読取専用", "自動取得", "-", "IF-010, IF-011", "-", "依存先結果"),
    ]


def build_rules() -> list[RuleSpec]:
    return [
        RuleSpec("RL-001", "認証", "ログイン時", "ユーザーが存在しない または password 不一致", "401 Incorrect username or password を返す", "app/api/v1/auth.py::login", "IF-001", "test_auth.py で確認"),
        RuleSpec("RL-002", "認証", "Bearer 認証", "token の署名・期限・sub 検証に失敗", "401 Could not validate credentials を返す", "app/core/security.py::decode_access_token", "IF-002, IF-003, IF-004, IF-005, IF-006, IF-007", "WWW-Authenticate=Bearer"),
        RuleSpec("RL-003", "認可", "文書登録/更新", "current_user.role が admin/editor 以外", "403 Not enough permissions を返す", "app/core/security.py::require_roles", "IF-003, IF-006", "viewer は不可"),
        RuleSpec("RL-004", "認可", "文書削除", "current_user.role が admin 以外", "403 Not enough permissions を返す", "app/core/security.py::require_roles", "IF-007", "editor も不可"),
        RuleSpec("RL-005", "入力制約", "文書一覧取得", "skip < 0 または limit が 1-100 の範囲外", "FastAPI / Query 制約で 422 とする", "app/api/v1/docs.py::list_docs", "IF-004", "仕様書では境界条件を明記"),
        RuleSpec("RL-006", "入力制約", "文書登録/更新", "title は 1-200 文字、content は 1 文字以上", "Pydantic Field 制約で検証する", "app/api/v1/docs.py::DocBase/DocUpdate", "IF-003, IF-006", "更新では未指定可"),
        RuleSpec("RL-007", "ヘルス", "ready/health", "database または qdrant のいずれかが error", "503 degraded と checks を返す", "app/api/v1/health.py::readiness", "IF-010, IF-011", "live は常に ok"),
        RuleSpec("RL-008", "RAG", "問合せ", "検索結果 source が 0 件", "『ドキュメントに該当する情報が見つかりませんでした。』を返す", "app/services/rag_service.py::ask", "IF-008", "幻覚抑制用"),
        RuleSpec("RL-009", "RAG", "問合せ", "search 実行時", "allowed_roles に user_roles のいずれかが含まれる point のみ取得", "app/services/rag_service.py::_search", "IF-008", "現状 role は request body 起点"),
        RuleSpec("RL-010", "Ingest", "再取込", "同じ source_file/source_key の既存 point が存在", "先に Qdrant delete を実行してから add する", "app/services/ingest_service.py::_delete_existing_points", "-", "重複登録防止"),
        RuleSpec("RL-011", "Excel Parser", "シート走査", "sheet_state != visible", "HIDDEN_SHEET_SKIPPED warning を追加し本文出力しない", "app/services/excel_parser.py::parse", "-", "Hidden sheet を安全に除外"),
        RuleSpec("RL-012", "Excel Parser", "セル読取", "cached 値なし + formula あり", "FORMULA_NO_CACHE warning と formula: =... を返す", "app/services/excel_parser.py::_read_cell_value", "-", "数式意味を保持"),
        RuleSpec("RL-013", "Excel Parser", "結合セル", "merged range を検出", "左上値を全域へ複製し MERGED_CELL_BROADCAST warning を追加", "app/services/excel_parser.py::_build_grid_with_merged_cells", "-", "神Excel対策"),
        RuleSpec("RL-014", "PDF Parser", "ページ読取", "text が少なく image が存在", "SCAN_PAGE_DETECTED warning を追加する", "app/services/pdf_parser.py::_detect_scan_page", "-", "OCR 予備判定"),
    ]


def build_errors(parser_warnings: Sequence[tuple[str, str]]) -> list[ErrorSpec]:
    warning_map = dict(parser_warnings)
    return [
        ErrorSpec("ERR-001", "HTTP", "app/api/v1/auth.py::login", _status_text(401), "Incorrect username or password", "ログイン認証失敗", "入力資格情報を再確認する", "認証系の代表エラー"),
        ErrorSpec("ERR-002", "HTTP", "app/core/security.py::decode_access_token", _status_text(401), "Could not validate credentials", "Bearer トークン検証失敗", "再ログインまたはトークン再取得", "WWW-Authenticate=Bearer"),
        ErrorSpec("ERR-003", "HTTP", "app/core/security.py::get_current_user", _status_text(401), "User not found", "token.sub に対応する User が見つからない", "DB の整合性を確認する", "-"),
        ErrorSpec("ERR-004", "HTTP", "app/core/security.py::require_roles", _status_text(403), "Not enough permissions", "許可ロール外で API 実行", "権限見直しまたは別ロールで実行", "docs 系で使用"),
        ErrorSpec("ERR-005", "HTTP", "app/api/v1/docs.py", _status_text(404), "Document not found", "指定 doc_id 不存在", "ID を確認する", "get/update/delete で共通"),
        ErrorSpec("ERR-006", "HTTP", "app/api/v1/rag.py::ask", _status_text(500), "RAG パイプラインでエラーが発生しました: {str(e)}", "RAG サービス例外", "OpenAI/Qdrant/設定値を確認する", "例外詳細は detail に埋め込む"),
        ErrorSpec("ERR-007", "HTTP", "app/api/v1/health.py::readiness", _status_text(503), '{"status":"degraded","checks":...}', "依存先のいずれかが異常", "database / qdrant の接続状態を確認する", "ready と health で共通"),
        ErrorSpec("ERR-008", "ParseError", "app/services/document_loader.py::load", "-", "ファイルが見つかりません: {file_path}", "対象ファイル不存在", "パスを確認する", "-"),
        ErrorSpec("ERR-009", "ParseError", "app/services/document_loader.py::load", "-", "サポートされていないファイル形式です: {ext}", "未対応拡張子", "対応形式を利用する", "-"),
        ErrorSpec("ERR-010", "ParseError", "app/services/document_loader.py::load", "-", "全てのパーサーが失敗しました", "フォールバックチェーン全失敗", "個別 parser error を確認する", "-"),
        ErrorSpec("ERR-011", "Warning", "app/services/parse_result.py::ParserWarning", "-", warning_map.get("HIDDEN_SHEET_SKIPPED", "-"), "非表示シートをスキップ", "仕様書としては hidden sheet を確認する", "warning 扱い"),
        ErrorSpec("ERR-012", "Warning", "app/services/parse_result.py::ParserWarning", "-", warning_map.get("MERGED_CELL_BROADCAST", "-"), "結合セルブロードキャスト", "結合範囲の設計意図を確認する", "warning 扱い"),
        ErrorSpec("ERR-013", "Warning", "app/services/parse_result.py::ParserWarning", "-", warning_map.get("FORMULA_NO_CACHE", "-"), "数式キャッシュ欠落", "再保存や再計算を行う", "warning 扱い"),
    ]


def build_test_points() -> list[TestPointSpec]:
    return [
        TestPointSpec("TC-001", "Auth", "tests/test_auth.py", "正しい資格情報で login 成功", "200 / access_token / role=admin", "IF-001", "RL-001", "test_login_success"),
        TestPointSpec("TC-002", "Auth", "tests/test_auth.py", "誤パスワードで login 失敗", "401 Incorrect username or password", "IF-001", "RL-001", "test_login_wrong_password"),
        TestPointSpec("TC-003", "Auth", "tests/test_auth.py", "Bearer 付きで me を取得", "200 / username / role", "IF-002", "RL-002", "test_me_success"),
        TestPointSpec("TC-004", "Docs", "tests/test_docs_auth.py", "未認証で docs 一覧", "401", "IF-004", "RL-002", "test_docs_requires_auth"),
        TestPointSpec("TC-005", "Docs", "tests/test_docs_auth.py", "viewer が文書作成を実行", "403 Not enough permissions", "IF-003", "RL-003", "test_viewer_cannot_create_doc"),
        TestPointSpec("TC-006", "Docs", "tests/test_docs_auth.py", "editor が文書作成を実行", "201 Created", "IF-003", "RL-003", "test_editor_can_create_doc"),
        TestPointSpec("TC-007", "Docs", "tests/test_docs_auth.py", "admin が文書削除を実行", "204 No Content", "IF-007", "RL-004", "test_admin_can_delete_doc"),
        TestPointSpec("TC-008", "Health", "tests/test_health.py", "liveness", "200 {status: ok}", "IF-009", "RL-007", "test_liveness"),
        TestPointSpec("TC-009", "Health", "tests/test_health.py", "readiness success", "200 status=ok", "IF-010", "RL-007", "test_readiness_success"),
        TestPointSpec("TC-010", "Health", "tests/test_health.py", "readiness degraded", "503 status=degraded", "IF-010, IF-011", "RL-007", "test_readiness_returns_503_when_dependency_fails"),
        TestPointSpec("TC-011", "Excel Parser", "tests/test_excel_parser.py", "結合セル値が消えない", "本文に結合セルタイトルが残る", "-", "RL-013", "test_merged_value_not_lost"),
        TestPointSpec("TC-012", "Excel Parser", "tests/test_excel_parser.py", "KV と Table の混在", "KV / Table 両方を検出", "-", "RL-011, RL-013", "test_kv_area_detected / test_table_area_detected"),
        TestPointSpec("TC-013", "Loader", "tests/test_document_loader.py", "対応拡張子以外を load", "ParseError", "-", "-", "test_unsupported_extension"),
        TestPointSpec("TC-014", "Ingest", "tests/test_ingest_service.py", "再取込時 delete 実行", "source_file/source_key で delete", "-", "RL-010", "test_ingest_deletes_existing_source_points"),
        TestPointSpec("TC-015", "Ingest", "tests/test_ingest_service.py", "metadata key 保持", "allowed_roles/chunk_index/source_key 等が保存", "-", "RL-009, RL-010", "test_ingest_metadata_keeps_expected_keys"),
    ]


def collect_repo_spec_data() -> RepoSpecBundle:
    endpoints = extract_endpoints()
    settings = extract_settings()
    constants = _extract_service_constants()
    return RepoSpecBundle(
        endpoints=endpoints,
        tables=extract_tables(),
        settings=settings,
        features=build_features(endpoints),
        screens=build_screens(),
        screen_items=build_screen_items(),
        rules=build_rules(),
        errors=build_errors(_extract_parser_warning_values()),
        test_points=build_test_points(),
        parser_warnings=_extract_parser_warning_values(),
        supported_extensions=_extract_document_loader_extensions(),
        vector_collection_name=constants.get("DEFAULT_COLLECTION", "documents"),
        vector_top_k=constants.get("DEFAULT_TOP_K", "5"),
        chunk_size=constants.get("CHUNK_SIZE", "500"),
        chunk_overlap=constants.get("CHUNK_OVERLAP", "100"),
        batch_size=constants.get("BATCH_SIZE", "64"),
        embedding_model=next((setting.example_value or setting.code_default for setting in settings if setting.field_name == "embedding_model"), "-"),
        embedding_dimensions=next((setting.example_value or setting.code_default for setting in settings if setting.field_name == "embedding_dimensions"), "-"),
        chat_model=next((setting.example_value or setting.code_default for setting in settings if setting.field_name == "chat_model"), "-"),
        vector_metadata=_extract_vector_metadata(),
    )


def _style_cell(
    cell: Cell,
    *,
    font: Font | None = None,
    fill: PatternFill | None = None,
    alignment: Alignment | None = None,
    border: Border | None = None,
) -> None:
    cell.font = font or Font(name=FONT_NAME, size=10)
    cell.fill = fill or PatternFill(fill_type=None)
    cell.alignment = alignment or Alignment(vertical="top", wrap_text=True)
    cell.border = border or DEFAULT_BORDER


def _fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color)


def _merged_block(
    worksheet: Worksheet,
    start_row: int,
    start_col: int,
    end_row: int,
    end_col: int,
    value: CellValue,
    *,
    font: Font | None = None,
    fill: PatternFill | None = None,
    alignment: Alignment | None = None,
) -> None:
    worksheet.merge_cells(start_row=start_row, start_column=start_col, end_row=end_row, end_column=end_col)
    cell = worksheet.cell(row=start_row, column=start_col, value=value)
    _style_cell(cell, font=font, fill=fill, alignment=alignment or Alignment(horizontal="center", vertical="center", wrap_text=True))


def _title_block(worksheet: Worksheet, end_col: int, title: str, subtitle: str) -> None:
    _merged_block(worksheet, 1, 1, 2, end_col, title, font=Font(name=FONT_NAME, bold=True, size=14, color=COLOR_WHITE), fill=_fill(COLOR_TITLE))
    _merged_block(worksheet, 3, 1, 3, end_col, subtitle, font=Font(name=FONT_NAME, size=10), fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center", wrap_text=True))


def _header_row(worksheet: Worksheet, row_index: int, headers: Sequence[str]) -> None:
    for column_index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=header)
        _style_cell(cell, font=Font(name=FONT_NAME, bold=True, size=10, color=COLOR_WHITE), fill=_fill("4472C4"), alignment=Alignment(horizontal="center", vertical="center", wrap_text=True))


def _fill_row(
    worksheet: Worksheet,
    row_index: int,
    values: Sequence[CellValue],
    *,
    fills: Sequence[str | None] | None = None,
    center_columns: set[int] | None = None,
) -> None:
    for column_index, value in enumerate(values, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=value)
        fill = None
        if fills and column_index - 1 < len(fills) and fills[column_index - 1]:
            fill = _fill(fills[column_index - 1] or "")
        alignment = Alignment(vertical="top", wrap_text=True)
        if center_columns and column_index in center_columns:
            alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        _style_cell(cell, fill=fill, alignment=alignment)


def _set_widths(worksheet: Worksheet, widths: Iterable[int]) -> None:
    for index, width in enumerate(widths, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = width


def _yes_no(value: bool) -> str:
    return "Y" if value else "N"


def _draw_input_box(worksheet: Worksheet, row: int, label: str, value: str, *, width_end: int = 10, required: bool = False) -> None:
    _merged_block(worksheet, row, 3, row, 5, label, fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, row, 6, row, width_end, value, fill=_fill(COLOR_REQUIRED if required else COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))


def _build_cover_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.active
    worksheet.title = "表紙・改定履歴"
    _title_block(worksheet, 12, "Role Aware RAG Platform 現状仕様書", "ソースコード / テスト / 設定例から自動生成した現行仕様。UI は全て推定UI。")
    _merged_block(worksheet, 5, 1, 5, 3, "文書情報", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _merged_block(worksheet, 5, 4, 5, 12, "Role Aware RAG Platform / FastAPI + SQLAlchemy + Qdrant", fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))
    summary_pairs = [
        ("生成日時", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "作成対象", "現状実装のみ"),
        ("仕様ソース", "app/, tests/, .env.example", "対象外", "plan.txt の将来計画"),
        ("機能数", "='集計_非表示'!B2", "IF 数", "='集計_非表示'!B3"),
        ("画面数", "='集計_非表示'!B4", "テーブル数", "='集計_非表示'!B5"),
        ("ルール数", "='集計_非表示'!B6", "エラー数", "='集計_非表示'!B7"),
    ]
    row = 7
    for left_key, left_value, right_key, right_value in summary_pairs:
        _fill_row(worksheet, row, [left_key, left_value, "", right_key, right_value, "", "", "", "", "", "", ""], fills=[COLOR_SECTION, COLOR_FORMULA, None, COLOR_SECTION, COLOR_FORMULA, None, None, None, None, None, None, None])
        worksheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
        worksheet.merge_cells(start_row=row, start_column=5, end_row=row, end_column=6)
        row += 1
    _merged_block(worksheet, 14, 1, 14, 12, "前提 / 実装差分メモ", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    notes = [
        "1. 真値優先度は実装コード + テスト > migration > 計画文書。",
        "2. users.role は実装上 admin/editor/viewer の小文字値だが、migration には大文字 enum 字面が残る。",
        "3. IF-008 RAG 問合せ は現状 Bearer 未接続で、body.role をそのままフィルタ条件に使う。",
    ]
    for index, note in enumerate(notes, start=15):
        _merged_block(worksheet, index, 1, index, 12, note, fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 20, 1, 20, 12, "改定履歴", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 21, ["版", "日付", "作成者", "変更内容", "", "", "", "", "", "", "", ""])
    _fill_row(worksheet, 22, ["1.0", datetime.now().strftime("%Y-%m-%d"), "Codex", "初版生成", "", "", "", "", "", "", "", ""])
    worksheet.freeze_panes = "A7"
    _set_widths(worksheet, [16, 18, 18, 16, 18, 18, 12, 12, 12, 12, 12, 12])


def _build_legend_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("凡例・採番")
    _title_block(worksheet, 10, "凡例・採番", "ID 体系と色分けルール。")
    _merged_block(worksheet, 5, 1, 5, 10, "採番体系", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 6, ["区分", "書式", "例", "用途", "備考", "", "", "", "", ""])
    numbering_rows = [
        ["機能ID", "FN-###", "FN-001", "機能一覧", "固定採番", "", "", "", "", ""],
        ["画面ID", "SCR-###", "SCR-001", "画面一覧 / 画面設計", "固定採番", "", "", "", "", ""],
        ["項目ID", "ITM-SCR###-###", "ITM-SCR001-001", "画面項目定義", "画面単位連番", "", "", "", "", ""],
        ["IF-ID", "IF-###", "IF-001", "IF一覧 / IF仕様", "公開 API 単位", "", "", "", "", ""],
        ["テーブルID", "TBL-###", "TBL-001", "テーブル一覧 / 定義", "物理テーブル単位", "", "", "", "", ""],
        ["カラムID", "COL-TBL###-###", "COL-TBL-001-001", "テーブル定義", "テーブル内連番", "", "", "", "", ""],
        ["ルールID", "RL-###", "RL-001", "業務・制御ルール", "条件表単位", "", "", "", "", ""],
        ["エラーID", "ERR-###", "ERR-001", "エラー一覧", "エラー/Warning 単位", "", "", "", "", ""],
        ["設定ID", "CFG-###", "CFG-001", "設定一覧", "設定項目単位", "", "", "", "", ""],
        ["テストID", "TC-###", "TC-001", "テスト観点", "観点単位", "", "", "", "", ""],
    ]
    for row_index, row_values in enumerate(numbering_rows, start=7):
        _fill_row(worksheet, row_index, row_values)
    _merged_block(worksheet, 19, 1, 19, 10, "色凡例", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 20, ["色", "用途", "説明", "", "", "", "", "", "", ""])
    color_rows = [
        (COLOR_TITLE, "タイトル", "シートタイトル / 大見出し"),
        (COLOR_SECTION, "節見出し", "セクション開始行"),
        (COLOR_REQUIRED, "必須", "入力必須項目"),
        (COLOR_READONLY, "読取専用", "更新不可 / 表示専用"),
        (COLOR_AUTO, "自動生成", "ID / 日時 / 自動計算"),
        (COLOR_AUTH, "認証/高権限", "Bearer / 権限要求関連"),
        (COLOR_FORMULA, "公式/参照", "数式・参照セル"),
    ]
    for row_index, (fill_color, label, desc) in enumerate(color_rows, start=21):
        _fill_row(worksheet, row_index, ["", label, desc, "", "", "", "", "", "", ""])
        _style_cell(worksheet.cell(row=row_index, column=1), fill=_fill(fill_color))
    worksheet.freeze_panes = "A6"
    _set_widths(worksheet, [12, 20, 42, 10, 10, 10, 10, 10, 10, 10])


def _build_feature_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("機能一覧")
    _title_block(worksheet, 10, "機能一覧", "公開 API と内部処理を含む現状機能マップ。")
    _header_row(worksheet, 5, ["機能ID", "機能名", "カテゴリ", "概要", "認可", "関連IF", "関連画面", "ソース", "備考", ""])
    for row_index, feature in enumerate(spec.features, start=6):
        fills = [None, None, None, None, COLOR_AUTH if "Bearer" in feature.auth_text else None, None, None, None, None, None]
        _fill_row(worksheet, row_index, [feature.feature_id, feature.name, feature.category, feature.summary, feature.auth_text, feature.related_if_ids, feature.screen_id, feature.source, feature.note, ""], fills=fills)
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 22, 16, 34, 20, 16, 12, 26, 38, 6])


def _build_screen_list_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("画面一覧")
    _title_block(worksheet, 8, "画面一覧", "後端実装から逆算した推定 UI 一覧。")
    _header_row(worksheet, 5, ["画面ID", "画面名", "概要", "認可", "関連IF", "備考", "", ""])
    for row_index, screen in enumerate(spec.screens, start=6):
        _fill_row(worksheet, row_index, [screen.screen_id, screen.name, screen.summary, screen.auth_text, screen.related_if_ids, screen.note, "", ""], fills=[None, None, None, COLOR_AUTH if "Bearer" in screen.auth_text else None, None, None, None, None])
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 24, 34, 18, 20, 28, 10, 10])


def _build_login_screen_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("画面設計_ログイン")
    _title_block(worksheet, 12, "画面設計_ログイン", "推定UI / IF-001, IF-002 に対応。")
    for row in range(5, 17):
        for col in range(3, 11):
            _style_cell(worksheet.cell(row=row, column=col), fill=_fill(COLOR_ALT))
    _merged_block(worksheet, 6, 3, 6, 10, "推定UI: ログインフォーム", font=Font(name=FONT_NAME, bold=True, size=12), fill=_fill(COLOR_SECTION))
    _draw_input_box(worksheet, 8, "Username", "例: testuser", required=True)
    _draw_input_box(worksheet, 10, "Password", "********", required=True)
    _merged_block(worksheet, 12, 4, 13, 9, "Login", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_AUTO))
    _merged_block(worksheet, 15, 3, 15, 10, "ログイン後は username / role のカードを表示", fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [6, 6, 12, 12, 12, 12, 12, 12, 12, 12, 6, 6])


def _build_docs_screen_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("画面設計_文書管理")
    _title_block(worksheet, 14, "画面設計_文書管理", "推定UI / IF-003 - IF-007 に対応。")
    _merged_block(worksheet, 5, 1, 5, 14, "推定UI: 左側一覧 + 右側編集フォーム", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    for row in range(6, 18):
        for col in range(1, 7):
            _style_cell(worksheet.cell(row=row, column=col), fill=_fill(COLOR_ALT))
        for col in range(7, 15):
            _style_cell(worksheet.cell(row=row, column=col), fill=_fill(COLOR_NOTE))
    _merged_block(worksheet, 7, 1, 7, 6, "文書一覧", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _merged_block(worksheet, 7, 7, 7, 14, "文書編集", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _merged_block(worksheet, 9, 1, 9, 3, "skip", fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 9, 4, 9, 6, "0", fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 10, 1, 10, 3, "limit", fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 10, 4, 10, 6, "10", fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 12, 2, 15, 5, "table: id / title / created_at / updated_at", fill=_fill(COLOR_READONLY), alignment=Alignment(horizontal="left", vertical="top"))
    _merged_block(worksheet, 9, 7, 9, 9, "Title", fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 9, 10, 9, 14, "文書タイトル", fill=_fill(COLOR_REQUIRED), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 11, 7, 11, 9, "Content", fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 11, 10, 12, 14, "複数行本文", fill=_fill(COLOR_REQUIRED), alignment=Alignment(horizontal="left", vertical="top"))
    _merged_block(worksheet, 14, 8, 15, 10, "Create", font=Font(name=FONT_NAME, bold=True, size=10), fill=_fill(COLOR_AUTO))
    _merged_block(worksheet, 14, 11, 15, 13, "Update", font=Font(name=FONT_NAME, bold=True, size=10), fill=_fill(COLOR_AUTO))
    _merged_block(worksheet, 16, 8, 17, 10, "Delete", font=Font(name=FONT_NAME, bold=True, size=10), fill=_fill(COLOR_AUTH))
    _merged_block(worksheet, 16, 11, 17, 13, "Detail", font=Font(name=FONT_NAME, bold=True, size=10), fill=_fill(COLOR_READONLY))
    worksheet.freeze_panes = "A6"
    _set_widths(worksheet, [10, 10, 10, 10, 10, 10, 12, 12, 12, 12, 12, 12, 12, 12])


def _build_rag_screen_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("画面設計_RAG問合せ")
    _title_block(worksheet, 14, "画面設計_RAG問合せ", "推定UI / IF-008 に対応。")
    _merged_block(worksheet, 5, 1, 5, 14, "推定UI: 問合せフォーム + 回答 + ソース一覧", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _draw_input_box(worksheet, 7, "Question", "売上レポートの作成方法は？", width_end=12, required=True)
    _draw_input_box(worksheet, 9, "Role", "viewer / editor / admin", width_end=9)
    _merged_block(worksheet, 9, 10, 10, 12, "Ask", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_AUTO))
    _merged_block(worksheet, 12, 1, 16, 14, "Answer Area\nここに生成回答を表示する", fill=_fill(COLOR_READONLY), alignment=Alignment(horizontal="left", vertical="top"))
    _merged_block(worksheet, 18, 1, 18, 14, "Sources", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 19, ["source_file", "chunk_index", "score", "text", "", "", "", "", "", "", "", "", "", ""])
    _merged_block(worksheet, 20, 1, 22, 14, "table rows rendered from AskResponse.sources", fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="top"))
    worksheet.freeze_panes = "A6"
    _set_widths(worksheet, [12, 12, 12, 14, 14, 14, 14, 12, 12, 12, 12, 12, 12, 12])


def _build_health_screen_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("画面設計_ヘルス監視")
    _title_block(worksheet, 12, "画面設計_ヘルス監視", "推定UI / IF-009 - IF-011 に対応。")
    _merged_block(worksheet, 5, 1, 5, 12, "推定UI: 監視ダッシュボード", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _merged_block(worksheet, 7, 2, 10, 5, "LIVE\nstatus=ok", font=Font(name=FONT_NAME, bold=True, size=12), fill=_fill(COLOR_AUTO))
    _merged_block(worksheet, 7, 7, 10, 10, "READY\ndatabase / qdrant", font=Font(name=FONT_NAME, bold=True, size=12), fill=_fill(COLOR_AUTH))
    _merged_block(worksheet, 12, 2, 13, 10, "checks.database / checks.qdrant を個別表示", fill=_fill(COLOR_NOTE), alignment=Alignment(horizontal="left", vertical="center"))
    _merged_block(worksheet, 15, 2, 16, 6, "Refresh", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_AUTO))
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [8, 12, 12, 12, 12, 8, 12, 12, 12, 12, 8, 8])


def _build_screen_item_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("画面項目定義")
    _title_block(worksheet, 17, "画面項目定義", "推定 UI 項目と IF / DB の対応。")
    _header_row(worksheet, 5, ["項目ID", "画面ID", "画面名", "項目名", "UI種別", "型", "桁数/上限", "必須", "初期値", "入力/表示ルール", "活性条件", "編集可否", "自動生成", "エラーメッセージ", "関連IF", "関連テーブル/カラム", "備考"])
    for row_index, item in enumerate(spec.screen_items, start=6):
        fills = [None, None, None, None, None, None, None, COLOR_REQUIRED if item.required_text == "Y" else None, None, None, None, COLOR_READONLY if item.editable_text == "読取専用" else None, COLOR_AUTO if item.auto_text != "-" else None, None, None, None, None]
        _fill_row(worksheet, row_index, [item.item_id, item.screen_id, item.screen_name, item.item_name, item.ui_type, item.type_name, item.length_text, item.required_text, item.default_text, item.rule_text, item.active_condition, item.editable_text, item.auto_text, item.error_message, item.related_if, item.related_column, item.note], fills=fills)
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [18, 12, 22, 18, 12, 14, 12, 8, 12, 24, 18, 12, 12, 28, 18, 24, 24])


def _build_if_list_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("IF一覧")
    _title_block(worksheet, 12, "IF一覧", "公開 API のサマリ一覧。")
    _header_row(worksheet, 5, ["IF-ID", "区分", "名称", "Method", "Path", "認可", "成功時", "Request", "Response", "画面", "機能", "備考"])
    for row_index, endpoint in enumerate(spec.endpoints, start=6):
        fills = [None, None, None, COLOR_AUTO, None, COLOR_AUTH if endpoint.auth_kind != "open" else None, None, None, None, None, None, None]
        _fill_row(worksheet, row_index, [endpoint.if_id, endpoint.group, endpoint.title, endpoint.method, endpoint.path, endpoint.auth_text, _status_text(endpoint.success_status), endpoint.request_model, endpoint.response_model, endpoint.screen_id, endpoint.feature_id, endpoint.note], fills=fills)
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 12, 20, 10, 28, 20, 14, 20, 20, 12, 12, 32])


def _detail_field_rows(fields: Sequence[ApiFieldSpec]) -> list[list[CellValue]]:
    if not fields:
        return [["-", "-", "-", "-", "-", "-", "-"]]
    return [[field_spec.name, field_spec.type_name, _yes_no(field_spec.required), field_spec.default_text, field_spec.rule_text, field_spec.description, field_spec.location] for field_spec in fields]


def _detail_error_rows(errors: Sequence[EndpointErrorSpec]) -> list[list[CellValue]]:
    if not errors:
        return [["-", "-", "-"]]
    return [[_status_text(error.status_code), error.detail, "-"] for error in errors]


def _append_detail_section(worksheet: Worksheet, start_row: int, title: str, headers: Sequence[str], rows: Sequence[Sequence[CellValue]]) -> int:
    _merged_block(worksheet, start_row, 1, start_row, len(headers), title, font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
    _header_row(worksheet, start_row + 1, headers)
    for offset, row in enumerate(rows, start=2):
        _fill_row(worksheet, start_row + offset, row)
    return start_row + len(rows) + 3


def _build_if_detail_sheet(workbook: Workbook, spec: RepoSpecBundle, group_name: str, title: str) -> None:
    worksheet = workbook.create_sheet(title)
    _title_block(worksheet, 10, title, f"{group_name} 系 API の詳細。")
    row = 5
    for endpoint in [item for item in spec.endpoints if item.group == group_name]:
        _merged_block(worksheet, row, 1, row, 10, f"{endpoint.if_id} {endpoint.title}", font=Font(name=FONT_NAME, bold=True, size=12), fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
        row += 1
        _fill_row(worksheet, row, ["Method", endpoint.method, "Path", endpoint.path, "認可", endpoint.auth_text, "成功時", _status_text(endpoint.success_status), "Handler", f"{endpoint.source_file}:{endpoint.line_no}"], fills=[COLOR_SECTION, COLOR_AUTO, COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_AUTH if endpoint.auth_kind != "open" else COLOR_NOTE, COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_NOTE])
        row += 2
        header_fields = [ApiFieldSpec("Authorization", "Bearer token", True, "-", "Bearer <token>", "認証ヘッダ", "header")] if endpoint.auth_kind != "open" else []
        row = _append_detail_section(worksheet, row, "Header", ["項目名", "型", "必須", "既定値", "ルール", "説明", "位置"], _detail_field_rows(header_fields))
        row = _append_detail_section(worksheet, row, "Path", ["項目名", "型", "必須", "既定値", "ルール", "説明", "位置"], _detail_field_rows(endpoint.path_params))
        row = _append_detail_section(worksheet, row, "Query", ["項目名", "型", "必須", "既定値", "ルール", "説明", "位置"], _detail_field_rows(endpoint.query_params))
        row = _append_detail_section(worksheet, row, "Body / Form", ["項目名", "型", "必須", "既定値", "ルール", "説明", "位置"], _detail_field_rows(endpoint.form_fields or endpoint.body_fields))
        row = _append_detail_section(worksheet, row, "Response", ["項目名", "型", "必須", "既定値", "ルール", "説明", "位置"], _detail_field_rows(endpoint.response_fields))
        row = _append_detail_section(worksheet, row, "Error", ["Status", "detail", "備考"], _detail_error_rows(endpoint.errors))
        row += 1
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [18, 20, 10, 14, 24, 34, 12, 18, 18, 22])


def _build_table_list_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("テーブル一覧")
    _title_block(worksheet, 8, "テーブル一覧", "SQLAlchemy モデル由来の物理テーブル一覧。")
    _header_row(worksheet, 5, ["TBL-ID", "テーブル名", "概要", "列数", "ソース", "備考", "", ""])
    for row_index, table_spec in enumerate(spec.tables, start=6):
        _fill_row(worksheet, row_index, [table_spec.table_id, table_spec.name, table_spec.summary, len(table_spec.columns), table_spec.source_file, "-", "", ""])
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 18, 32, 10, 24, 20, 10, 10])


def _build_table_definition_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("テーブル定義")
    _title_block(worksheet, 12, "テーブル定義", "現行 SQLAlchemy モデルの列定義。")
    row = 5
    for table_spec in spec.tables:
        _merged_block(worksheet, row, 1, row, 12, f"{table_spec.table_id} {table_spec.name}", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION), alignment=Alignment(horizontal="left", vertical="center"))
        row += 1
        _fill_row(worksheet, row, ["概要", table_spec.summary, "ソース", table_spec.source_file, "", "", "", "", "", "", "", ""], fills=[COLOR_SECTION, COLOR_NOTE, COLOR_SECTION, COLOR_NOTE, None, None, None, None, None, None, None, None])
        row += 1
        _header_row(worksheet, row, ["COL-ID", "カラム名", "型", "Python型", "長さ", "PK", "UK", "NULL", "既定値", "自動/更新", "説明", "備考"])
        for column_spec in table_spec.columns:
            row += 1
            fills = [None, None, None, None, None, COLOR_AUTO if column_spec.primary_key else None, None, None, COLOR_FORMULA if column_spec.default_text != "-" else None, COLOR_AUTO if column_spec.auto_text != "-" else None, None, None]
            _fill_row(worksheet, row, [column_spec.column_id, column_spec.name, column_spec.type_name, column_spec.python_type, column_spec.length_text, _yes_no(column_spec.primary_key), _yes_no(column_spec.unique), _yes_no(column_spec.nullable), column_spec.default_text, column_spec.auto_text, column_spec.description, column_spec.note], fills=fills)
        row += 2
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [16, 16, 18, 14, 10, 8, 8, 8, 18, 18, 20, 32])


def _build_vector_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("ベクトルストア仕様")
    _title_block(worksheet, 10, "ベクトルストア仕様", "Qdrant collection / metadata / chunking の現状。")
    _merged_block(worksheet, 5, 1, 5, 10, "Collection / Retrieval", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _fill_row(worksheet, 6, ["collection_name", spec.vector_collection_name, "top_k", spec.vector_top_k, "embedding_model", spec.embedding_model, "embedding_dimensions", spec.embedding_dimensions, "chat_model", spec.chat_model], fills=[COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_NOTE, COLOR_SECTION, COLOR_NOTE, COLOR_SECTION, COLOR_NOTE])
    _fill_row(worksheet, 7, ["chunk_size", spec.chunk_size, "chunk_overlap", spec.chunk_overlap, "batch_size", spec.batch_size, "supported_extensions", ", ".join(spec.supported_extensions), "", ""], fills=[COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_FORMULA, COLOR_SECTION, COLOR_NOTE, None, None])
    _merged_block(worksheet, 10, 1, 10, 10, "Payload Metadata", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 11, ["項目", "型", "必須", "説明", "実装ソース", "", "", "", "", ""])
    for row_index, metadata in enumerate(spec.vector_metadata, start=12):
        _fill_row(worksheet, row_index, [metadata.name, metadata.type_name, _yes_no(metadata.required), metadata.description, metadata.source, "", "", "", "", ""], fills=[None, None, COLOR_REQUIRED if metadata.required else None, None, None, None, None, None, None, None])
    _merged_block(worksheet, 20, 1, 20, 10, "検索制御", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 21, ["観点", "内容", "ソース", "", "", "", "", "", "", ""])
    search_rows = [
        ["role filter", "Filter.must -> allowed_roles MatchAny(any=user_roles)", "app/services/rag_service.py::_search", "", "", "", "", "", "", ""],
        ["source text", "_node_content があれば JSON から text を抽出", "app/services/rag_service.py::_extract_text", "", "", "", "", "", "", ""],
        ["再取込削除", "source_file / source_key で delete", "app/services/ingest_service.py::_delete_existing_points", "", "", "", "", "", "", ""],
    ]
    for row_index, row_values in enumerate(search_rows, start=22):
        _fill_row(worksheet, row_index, row_values)
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [18, 30, 14, 28, 16, 16, 14, 20, 14, 14])


def _build_auth_matrix_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("認可マトリクス")
    _title_block(worksheet, 9, "認可マトリクス", "公開 API ごとの実効アクセス可否。")
    _header_row(worksheet, 5, ["IF-ID", "名称", "Path", "匿名", "admin", "editor", "viewer", "認可方式", "備考"])
    for row_index, endpoint in enumerate(spec.endpoints, start=6):
        anonymous, admin, editor, viewer = ("Y", "Y", "Y", "Y") if endpoint.auth_kind == "open" else ("N", "Y", "Y", "Y")
        if endpoint.auth_kind == "role" and endpoint.if_id in {"IF-003", "IF-006"}:
            viewer = "N"
        if endpoint.auth_kind == "role" and endpoint.if_id == "IF-007":
            editor = "N"
            viewer = "N"
        _fill_row(worksheet, row_index, [endpoint.if_id, endpoint.title, endpoint.path, anonymous, admin, editor, viewer, endpoint.auth_text, endpoint.note], fills=[None, None, None, COLOR_AUTO if anonymous == "Y" else COLOR_READONLY, COLOR_AUTO, COLOR_AUTO if editor == "Y" else COLOR_READONLY, COLOR_AUTO if viewer == "Y" else COLOR_READONLY, COLOR_AUTH if endpoint.auth_kind != "open" else None, None], center_columns={4, 5, 6, 7})
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 18, 30, 10, 10, 10, 10, 24, 30])


def _build_rule_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("業務・制御ルール")
    _title_block(worksheet, 8, "業務・制御ルール", "条件表で表す業務・制御ロジック。")
    _header_row(worksheet, 5, ["RL-ID", "カテゴリ", "条件", "When", "Then", "ソース", "関連IF", "備考"])
    for row_index, rule in enumerate(spec.rules, start=6):
        _fill_row(worksheet, row_index, [rule.rule_id, rule.category, rule.condition, rule.when_text, rule.then_text, rule.source, rule.related_if, rule.note])
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 14, 16, 28, 34, 30, 18, 28])


def _build_flow_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("処理フロー")
    _title_block(worksheet, 9, "処理フロー", "Ingest 系と Query 系の 2 スイムレーン。")
    _merged_block(worksheet, 5, 1, 5, 9, "Ingest フロー", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 6, ["Lane", "Step", "主体", "処理", "入力", "出力", "関連ルール", "関連機能", "備考"])
    for row_index, row_values in enumerate([
        ["Ingest", "1", "DocumentLoader", "拡張子で parser chain を選択", "file_path", "ParseResult", "RL-011, RL-012, RL-013", "FN-009, FN-010, FN-011", "フォールバックあり"],
        ["Ingest", "2", "IngestService", "既存 point を delete", "source_file/source_key", "clean collection", "RL-010", "FN-009", "再取込対応"],
        ["Ingest", "3", "Splitter", "chunk 化", "ParseResult.text", "TextNode[]", "-", "FN-009", "chunk_size=500"],
        ["Ingest", "4", "OpenAIEmbedding", "embedding 生成", "TextNode[]", "embedded nodes", "-", "FN-009", "dimensions=1536"],
        ["Ingest", "5", "QdrantVectorStore", "point add", "embedded nodes", "Qdrant points", "RL-010", "FN-009", "payload 付与"],
    ], start=7):
        _fill_row(worksheet, row_index, row_values, fills=[COLOR_SECTION, COLOR_AUTO, None, None, None, None, None, None, None])
    _merged_block(worksheet, 15, 1, 15, 9, "Query フロー", font=Font(name=FONT_NAME, bold=True, size=11), fill=_fill(COLOR_SECTION))
    _header_row(worksheet, 16, ["Lane", "Step", "主体", "処理", "入力", "出力", "関連ルール", "関連機能", "備考"])
    for row_index, row_values in enumerate([
        ["Query", "1", "RAG API", "question / role 受領", "AskRequest", "question, user_roles", "-", "FN-008", "現状は公開 API"],
        ["Query", "2", "RagService", "query embedding", "question", "vector", "-", "FN-008", "OpenAI embeddings"],
        ["Query", "3", "Qdrant", "role filter 付き検索", "vector + allowed_roles", "source chunks", "RL-009", "FN-008", "top_k=5"],
        ["Query", "4", "RagService", "prompt 組立", "question + source chunks", "user_message", "RL-008", "FN-008", "出典付き context"],
        ["Query", "5", "ChatCompletion", "回答生成", "system + user message", "answer", "RL-008", "FN-008", "temperature=0.3"],
    ], start=17):
        _fill_row(worksheet, row_index, row_values, fills=[COLOR_SECTION, COLOR_AUTO, None, None, None, None, None, None, None])
    worksheet.freeze_panes = "A6"
    _set_widths(worksheet, [12, 8, 16, 28, 24, 24, 18, 18, 24])


def _build_setting_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("設定一覧")
    _title_block(worksheet, 11, "設定一覧", "BaseSettings と `.env.example` の現在値。")
    _header_row(worksheet, 5, ["CFG-ID", "クラス", "項目", "ENV 名", "型", "必須", "コード既定値", "例示値(.env.example)", "説明", "モジュール", "備考"])
    for row_index, setting in enumerate(spec.settings, start=6):
        fills = [None, None, None, None, None, COLOR_REQUIRED if setting.required else None, COLOR_FORMULA if setting.code_default != "-" else None, COLOR_NOTE if setting.example_value else None, None, None, None]
        _fill_row(worksheet, row_index, [setting.setting_id, setting.class_name, setting.field_name, setting.env_name, setting.type_name, _yes_no(setting.required), setting.code_default, setting.example_value, setting.description, setting.module_path, setting.note], fills=fills)
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 18, 18, 22, 16, 8, 18, 28, 28, 26, 28])


def _build_error_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("エラー一覧")
    _title_block(worksheet, 10, "エラー一覧", "HTTP / ParseError / Warning の代表一覧。")
    _header_row(worksheet, 5, ["ERR-ID", "区分", "ソース", "Status", "メッセージ", "契機", "復旧方針", "備考", "", ""])
    for row_index, error in enumerate(spec.errors, start=6):
        fills = [None, None, None, COLOR_AUTH if error.status_text.startswith(("401", "403")) else None, None, None, None, None, None, None]
        _fill_row(worksheet, row_index, [error.error_id, error.category, error.source, error.status_text, error.message, error.trigger, error.recovery, error.note, "", ""], fills=fills)
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 12, 28, 16, 36, 24, 28, 24, 10, 10])


def _build_test_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("テスト観点")
    _title_block(worksheet, 9, "テスト観点", "既存テストから拾った代表観点。")
    _header_row(worksheet, 5, ["TC-ID", "領域", "ソース", "シナリオ", "期待結果", "関連IF", "関連Rule", "備考", ""])
    for row_index, test_point in enumerate(spec.test_points, start=6):
        _fill_row(worksheet, row_index, [test_point.test_id, test_point.area, test_point.source_file, test_point.scenario, test_point.expected, test_point.related_if, test_point.related_rule, test_point.note, ""])
    worksheet.freeze_panes = "A5"
    _set_widths(worksheet, [12, 14, 26, 24, 28, 18, 18, 24, 10])


def _build_id_master_sheet(workbook: Workbook, spec: RepoSpecBundle) -> None:
    worksheet = workbook.create_sheet("採番マスタ_非表示")
    worksheet.sheet_state = "hidden"
    worksheet["A1"] = "区分"
    worksheet["B1"] = "ID"
    worksheet["C1"] = "名称"
    row = 2
    for feature in spec.features:
        worksheet[f"A{row}"] = "FN"
        worksheet[f"B{row}"] = feature.feature_id
        worksheet[f"C{row}"] = feature.name
        row += 1
    for screen in spec.screens:
        worksheet[f"A{row}"] = "SCR"
        worksheet[f"B{row}"] = screen.screen_id
        worksheet[f"C{row}"] = screen.name
        row += 1
    for endpoint in spec.endpoints:
        worksheet[f"A{row}"] = "IF"
        worksheet[f"B{row}"] = endpoint.if_id
        worksheet[f"C{row}"] = endpoint.title
        row += 1
    for table in spec.tables:
        worksheet[f"A{row}"] = "TBL"
        worksheet[f"B{row}"] = table.table_id
        worksheet[f"C{row}"] = table.name
        row += 1


def _build_aggregate_sheet(workbook: Workbook) -> None:
    worksheet = workbook.create_sheet("集計_非表示")
    worksheet.sheet_state = "hidden"
    worksheet["A1"] = "Metric"
    worksheet["B1"] = "Value"
    for row_index, (label, formula) in enumerate([
        ("機能数", "=COUNTA('機能一覧'!A6:A200)"),
        ("IF数", "=COUNTA('IF一覧'!A6:A200)"),
        ("画面数", "=COUNTA('画面一覧'!A6:A200)"),
        ("テーブル数", "=COUNTA('テーブル一覧'!A6:A200)"),
        ("ルール数", "=COUNTA('業務・制御ルール'!A6:A200)"),
        ("エラー数", "=COUNTA('エラー一覧'!A6:A200)"),
    ], start=2):
        worksheet[f"A{row_index}"] = label
        worksheet[f"B{row_index}"] = formula


def create_workbook(spec: RepoSpecBundle) -> Workbook:
    workbook = Workbook()
    _build_cover_sheet(workbook, spec)
    _build_legend_sheet(workbook)
    _build_feature_sheet(workbook, spec)
    _build_screen_list_sheet(workbook, spec)
    _build_login_screen_sheet(workbook)
    _build_docs_screen_sheet(workbook)
    _build_rag_screen_sheet(workbook)
    _build_health_screen_sheet(workbook)
    _build_screen_item_sheet(workbook, spec)
    _build_if_list_sheet(workbook, spec)
    _build_if_detail_sheet(workbook, spec, "Auth", "IF仕様_Auth")
    _build_if_detail_sheet(workbook, spec, "Docs", "IF仕様_Docs")
    _build_if_detail_sheet(workbook, spec, "RAG", "IF仕様_RAG")
    _build_if_detail_sheet(workbook, spec, "Health", "IF仕様_Health")
    _build_table_list_sheet(workbook, spec)
    _build_table_definition_sheet(workbook, spec)
    _build_vector_sheet(workbook, spec)
    _build_auth_matrix_sheet(workbook, spec)
    _build_rule_sheet(workbook, spec)
    _build_flow_sheet(workbook)
    _build_setting_sheet(workbook, spec)
    _build_error_sheet(workbook, spec)
    _build_test_sheet(workbook, spec)
    _build_id_master_sheet(workbook, spec)
    _build_aggregate_sheet(workbook)
    return workbook


def _save_workbook_with_fallback(workbook: Workbook, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        workbook.save(output_path)
        return output_path
    except PermissionError:
        fallback_path = output_path.with_name(f"{output_path.stem}.generated{output_path.suffix}")
        workbook.save(fallback_path)
        return fallback_path


def write_repo_spec_workbook(output_path: Path | None = None) -> Path:
    workbook = create_workbook(collect_repo_spec_data())
    saved_path = _save_workbook_with_fallback(workbook, output_path or DEFAULT_OUTPUT_PATH)
    workbook.close()
    return saved_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create repository spec workbook.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    print(f"Created: {write_repo_spec_workbook(args.output)}")


if __name__ == "__main__":
    main()
