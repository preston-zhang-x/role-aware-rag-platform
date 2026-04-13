import {
  ClipboardCheck,
  Coins,
  Database,
  FileSpreadsheet,
  Languages,
  SearchCheck,
  ShieldCheck,
  Workflow,
} from "lucide-react"

import { AppShell } from "@/components/layout/app-shell"
import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { LoginForm } from "@/features/auth/components/login-form"

export default function LoginPage() {
  return (
    <AppShell
      header={
        <PageHeader
          eyebrow="ACCESS"
          title="社内検索RAGシステムのログイン"
          description="社内文書を役割ごとに絞り込んで検索し、回答と出典をあわせて確認できる RAG システムです。複雑な日本式 Excel 設計書や PDF の解析にも対応しています。"
          actions={<Badge variant="secondary">role-aware access</Badge>}
        />
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_380px] xl:items-start">
        <section className="space-y-6">
          <Card className="border-white/70">
            <CardHeader>
              <CardTitle className="text-lg">主な特長</CardTitle>
              <CardDescription>
                社内ナレッジ検索を実運用するうえで重要なポイントを、同じ UI トーンで整理しています。
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-2xl border bg-white/70 p-4">
                <ShieldCheck className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">役割別の検索制御</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  ユーザーの権限に応じて、検索対象となる文書範囲を自動で切り替えます。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <Database className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">回答と出典の対応</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  回答本文と参照元の資料をあわせて確認でき、根拠を追跡しやすくしています。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <ShieldCheck className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">モデル構成を柔軟に切り替え</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  情報セキュリティ要件に応じてローカル LLM と外部 LLM を切り替えられ、機密性を確保しながら精度とコストのバランスを調整できます。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <Languages className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">日本語特化の検索処理</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  日本語文書の検索を前提に、形態素解析や文書構造を考慮した処理を組み込んでいます。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <FileSpreadsheet className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">日本式 Excel 設計書対応</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  複雑なシート構成や結合セルを含む日本式 Excel 設計書、PDF 文書の解析に対応しています。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <Coins className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">トークン使用量とコスト監視</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  latency と token 情報を確認できるため、応答性能と推論コストの両方を把握しやすくしています。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <SearchCheck className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">複数検索モードに対応</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  vector、BM25、hybrid、hybrid rerank を切り替えながら、用途に合った検索品質を比較できます。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <ClipboardCheck className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">評価データセットで精度検証</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  評価データセットとレポートを使って、検索精度や回答品質を継続的に確認できます。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <Workflow className="size-5 text-primary" />
                <p className="mt-3 text-sm font-semibold text-slate-900">フォールバックで高い互換性</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  取り込み時に想定どおり解析できない文書でも別処理へ自動でフォールバックし、対応可能な文書形式の幅を広げています。
                </p>
              </div>
            </CardContent>
          </Card>
        </section>

        <aside className="xl:sticky xl:top-6">
          <LoginForm />
        </aside>
      </div>
    </AppShell>
  )
}
