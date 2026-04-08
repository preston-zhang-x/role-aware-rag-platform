import { Bot, Coins, Database, Gauge, SendHorizonal } from "lucide-react"
import { Link } from "react-router-dom"

import { AppShell } from "@/components/layout/app-shell"
import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"

export default function ChatPage() {
  return (
    <AppShell
      header={
        <PageHeader
          eyebrow="CHAT"
          title="ナレッジ問い合わせワークスペース"
          description="質問、回答、参照資料を 1 画面で確認できる問い合わせビューです。"
          actions={
            <>
              <Badge variant="secondary">role-based UI</Badge>
              <Button asChild variant="outline">
                <Link to="/login">ログイン画面に戻る</Link>
              </Button>
            </>
          }
        />
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_360px]">
        <section className="space-y-6">
          <Card className="border-white/70">
            <CardHeader className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">会話プレビュー</Badge>
                <Badge variant="outline">回答と出典</Badge>
              </div>
              <CardTitle className="text-lg">AI チャット</CardTitle>
              <CardDescription>
                社内文書を参照しながら、質問と回答が自然な会話の流れで並ぶレイアウトです。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-5">
                <div className="flex justify-end">
                  <div className="max-w-[88%] space-y-2">
                    <div className="flex items-center justify-end gap-2 text-xs text-slate-500">
                      <span>あなた</span>
                      <span className="flex size-8 items-center justify-center rounded-2xl bg-slate-900 text-[11px] font-semibold tracking-[0.12em] text-white">
                        YOU
                      </span>
                    </div>
                    <div className="rounded-[26px] rounded-tr-md bg-slate-900 px-5 py-4 text-sm leading-7 text-white shadow-[0_22px_44px_-32px_rgba(15,23,42,0.9)]">
                      4 月度の売上レポートを作成したいです。集計の手順と、確認しておくべき資料を教えてください。
                    </div>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Bot className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="font-medium text-slate-800">AI アシスタント</span>
                      <Badge variant="outline">回答プレビュー</Badge>
                    </div>

                    <div className="rounded-[26px] rounded-tl-md border bg-white px-5 py-4 shadow-[0_18px_36px_-28px_rgba(15,23,42,0.35)]">
                      <div className="space-y-3 text-sm leading-7 text-slate-700">
                        <p>
                          4 月度の売上レポートは、まず集計条件を確認したうえで、出力手順に沿って進めるとスムーズです。
                        </p>
                        <ol className="list-decimal space-y-1.5 pl-5">
                          <li>
                            `finance_report.xlsx` の「基本設計」シートで対象期間と集計項目を確認します。
                          </li>
                          <li>売上データを抽出し、必要な列をレポート形式に整えます。</li>
                          <li>
                            `ops_manual.pdf` の手順に沿って、出力設定と提出前の確認項目をチェックします。
                          </li>
                        </ol>
                        <p>
                          必要であれば、このまま「提出前チェック項目」や「集計対象の定義」まで続けて案内できます。
                        </p>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span className="rounded-full border bg-slate-50 px-3 py-1.5">
                          latency 1.2s
                        </span>
                        <span className="rounded-full border bg-slate-50 px-3 py-1.5">
                          prompt 812 tokens
                        </span>
                        <span className="rounded-full border bg-slate-50 px-3 py-1.5">
                          completion 236 tokens
                        </span>
                      </div>
                    </div>

                  </div>
                </div>
              </div>

              <Separator />

              <div className="rounded-[28px] border bg-slate-50/90 p-4 shadow-inner shadow-white/80">
                <Textarea
                  placeholder="続けて質問してください。例: 提出前の確認項目だけを箇条書きでまとめてください。"
                  className="min-h-[116px] resize-none border-0 bg-transparent px-0 py-0 shadow-none focus-visible:border-transparent focus-visible:ring-0"
                />
                <div className="mt-4 flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    送信すると、この下に次のユーザーメッセージと AI の回答が続く想定です。
                  </p>
                  <Button disabled size="lg">
                    <SendHorizonal className="size-4" />
                    送信
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <aside className="space-y-6">
          <Card className="border-white/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Database className="size-5 text-primary" />
                参照資料プレビュー
              </CardTitle>
              <CardDescription>
                直前の回答で参照した `sources` をここにまとめて表示します。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border bg-white/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-slate-900">finance_report.xlsx</p>
                  <Badge variant="outline">手順 1</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-600">シート: 基本設計 / セル: A1:B3</p>
                <p className="mt-3 text-sm leading-6 text-slate-700">
                  集計対象、対象期間、レポート項目の定義を確認するために参照した箇所です。
                </p>
              </div>

              <div className="rounded-2xl border bg-white/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-slate-900">ops_manual.pdf</p>
                  <Badge variant="secondary">手順 3</Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-700">
                  出力手順と提出前チェックの流れを確認するために参照した資料です。
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Gauge className="size-5 text-primary" />
                応答メトリクス
              </CardTitle>
              <CardDescription>
                直近の回答に紐づく latency と token 使用量をまとめて確認できます。
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border bg-white/80 p-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Prompt Tokens
                      </p>
                      <p className="mt-2.5 text-xl font-semibold tracking-tight text-slate-900">
                        812
                      </p>
                    </div>
                    <div className="flex size-9 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <Coins className="size-4" />
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border bg-white/80 p-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Completion Tokens
                      </p>
                      <p className="mt-2.5 text-xl font-semibold tracking-tight text-slate-900">
                        236
                      </p>
                    </div>
                    <div className="flex size-9 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <Bot className="size-4" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border bg-white/80 p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Latency
                    </p>
                    <p className="mt-2.5 text-xl font-semibold tracking-tight text-slate-900">
                      1.2s
                    </p>
                    <p className="mt-1.5 text-xs leading-5 text-slate-600">
                      応答完了までのおおよその処理時間です。
                    </p>
                  </div>
                  <div className="flex size-9 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Gauge className="size-4" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </AppShell>
  )
}
