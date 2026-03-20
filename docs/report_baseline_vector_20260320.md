# Week02 Baseline 評測レポート

**実行日時**: 2026-03-20 00:25:13
**実行モード**: `admin-only evaluation`
**API エンドポイント**: `http://localhost:8000/api/v1/rag/ask`
**認証エンドポイント**: `http://localhost:8000/api/v1/auth/login`
**実行権限**: `admin`

## サマリー

| 指標 | 値 |
|------|-----|
| 総問題数 | 40 |
| HIT（正解） | 26 |
| MISS（不正解） | 14 |
| ERROR | 0 |
| **正解率** | **65.0%** |

## Requested Role 別集計

| Requested Role | Total | HIT | MISS | ERROR |
|----------------|-------|-----|------|-------|
| admin | 30 | 17 | 13 | 0 |
| manager | 4 | 4 | 0 | 0 |
| staff | 6 | 5 | 1 | 0 |

## Miss Reason 別集計

| Miss Reason | Count |
|-------------|-------|
| not_found_answer | 10 |
| keyword_mismatch | 4 |

## 詳細結果

| ID | Question | Requested Role | Executed As | Hit | Sources | Miss Reason | Error |
|----|----------|----------------|-------------|-----|---------|-------------|-------|
| 1 | 仕様書のタイトルは何ですか？ | admin | admin | HIT | 5 | - | - |
| 2 | 作成対象は何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 3 | FN-007 の機能名は何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 4 | FN-010 のカテゴリは何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 5 | FN-012 の備考では異常時に何を返すとありますか？ | admin | admin | HIT | 5 | - | - |
| 6 | SCR-003 の画面名は何ですか？ | admin | admin | HIT | 5 | - | - |
| 7 | ITM-SCR003-002 は何を表示しますか？ | admin | admin | MISS | 5 | keyword_mismatch | - |
| 8 | IF-007 の HTTP メソッドは何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 9 | IF-010 の Path は何ですか？ | admin | admin | HIT | 5 | - | - |
| 10 | IF-001 の response に含まれるトークン種別の... | admin | admin | MISS | 5 | keyword_mismatch | - |
| 11 | IF-004 の query parameter `limi... | admin | admin | HIT | 5 | - | - |
| 12 | IF-004 の `limit` の上限は何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 13 | IF-005 の path parameter 名は何ですか... | admin | admin | MISS | 5 | not_found_answer | - |
| 14 | IF-007 の成功時ステータスは何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 15 | IF-008 の request body フィールド名は何... | admin | admin | HIT | 5 | - | - |
| 16 | IF-010 の異常時ステータスは何ですか？ | admin | admin | MISS | 5 | keyword_mismatch | - |
| 17 | users テーブルの `role` カラムの既定値は何です... | admin | admin | HIT | 5 | - | - |
| 18 | documents.updated_at の自動/更新は何で... | admin | admin | MISS | 5 | keyword_mismatch | - |
| 19 | ベクトルストアの collection_name は何ですか... | admin | admin | HIT | 5 | - | - |
| 20 | chunk_overlap は何ですか？ | admin | admin | MISS | 5 | not_found_answer | - |
| 21 | chat_model は何ですか？ | admin | admin | HIT | 5 | - | - |
| 22 | ロールフィルタ対象の payload metadata 項目... | admin | admin | HIT | 5 | - | - |
| 23 | RL-012 の warning 名は何ですか？ | admin | admin | HIT | 5 | - | - |
| 24 | Query フロー Step 3 の主体は何ですか？ | admin | admin | HIT | 5 | - | - |
| 25 | OPENAI_BASE_URL の例示値は何ですか？ | admin | admin | HIT | 5 | - | - |
| 26 | IF-003 の成功時ステータスは何ですか？ | manager | admin | HIT | 5 | - | - |
| 27 | IF-006 の認可は何ですか？ | manager | admin | HIT | 5 | - | - |
| 28 | IF-009 の名称は何ですか？ | staff | admin | HIT | 5 | - | - |
| 29 | SCR-004 の画面名は何ですか？ | staff | admin | HIT | 5 | - | - |
| 30 | CFG-002 のコード既定値は何ですか？ | staff | admin | HIT | 5 | - | - |
| 31 | IF-008 の認証方法と検索時ロールの決定元は何ですか？ | admin | admin | HIT | 5 | - | - |
| 32 | JWT に含めるクレームは何ですか？ | admin | admin | HIT | 5 | - | - |
| 33 | IF-003 と IF-006 を実行できるロールは何ですか... | manager | admin | HIT | 5 | - | - |
| 34 | users.role の実装値は何ですか？ | staff | admin | HIT | 5 | - | - |
| 35 | ACCESS_TOKEN_EXPIRE_MINUTES のコ... | staff | admin | MISS | 5 | not_found_answer | - |
| 36 | RAG 検索の metadata フィルタ項目名と型は何です... | admin | admin | HIT | 5 | - | - |
| 37 | 再取込時に既存ポイントを識別して削除する metadata ... | manager | admin | HIT | 5 | - | - |
| 38 | 結合セル検出時に追加される warning 名は何ですか？ | admin | admin | HIT | 5 | - | - |
| 39 | health 系で degraded を返す HTTP ステ... | staff | admin | HIT | 5 | - | - |
| 40 | RAG の response sources に含まれる項目... | admin | admin | MISS | 5 | not_found_answer | - |

## 非 HIT 詳細分析

### Q2: 作成対象は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: 現状実装のみ
- **不足キーワード**: 現状実装のみ
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q3: FN-007 の機能名は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: 文書削除
- **不足キーワード**: 文書削除
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q4: FN-010 のカテゴリは何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: Parser
- **不足キーワード**: Parser
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q7: ITM-SCR003-002 は何を表示しますか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: keyword_mismatch
- **期待キーワード**: 現在ログイン中ユーザーの role を表示
- **不足キーワード**: 現在ログイン中ユーザーの role を表示
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ITM-SCR003-002は、現在ログイン中ユーザーのroleを表示します。出典は【参考2】です。

### Q8: IF-007 の HTTP メソッドは何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: DELETE
- **不足キーワード**: DELETE
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q10: IF-001 の response に含まれるトークン種別の項目名は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: keyword_mismatch
- **期待キーワード**: token_type
- **不足キーワード**: token_type
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: IF-001 の response に含まれるトークン種別の項目名は「Token」です。（出典: 参考2）

### Q12: IF-004 の `limit` の上限は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: 100
- **不足キーワード**: 100
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。（出典: docs/role_aware_rag_platform_spec.xlsx）

### Q13: IF-005 の path parameter 名は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: doc_id
- **不足キーワード**: doc_id
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q14: IF-007 の成功時ステータスは何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: 204, No, Content
- **不足キーワード**: 204, No, Content
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q16: IF-010 の異常時ステータスは何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: keyword_mismatch
- **期待キーワード**: 503, Service, Unavailable
- **不足キーワード**: Service, Unavailable
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: IF-010 の異常時ステータスは「503 degraded」です。（出典: 参考1）

### Q18: documents.updated_at の自動/更新は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: keyword_mismatch
- **期待キーワード**: server_default, onupdate
- **不足キーワード**: server_default, onupdate
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: documents.updated_at の自動/更新は「func.now()」であり、これは更新日時を自動的に現在の日時に設定することを意味します。（出典: 参考1）

### Q20: chunk_overlap は何ですか？
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: 100
- **不足キーワード**: 100
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q35: ACCESS_TOKEN_EXPIRE_MINUTES のコード既定値は何分ですか？
- **Requested Role**: staff
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: 30
- **不足キーワード**: 30
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

### Q40: RAG の response sources に含まれる項目を 2 つ挙げてください。
- **Requested Role**: admin
- **Executed As**: admin
- **Miss Reason**: not_found_answer
- **期待キーワード**: source_file, chunk_index
- **不足キーワード**: source_file, chunk_index
- **先頭 Source**: docs/role_aware_rag_platform_spec.xlsx
- **実際の回答**: ドキュメントに該当する情報が見つかりませんでした。

---
*Generated by `script/run_eval.py` at 2026-03-20 00:25:13*