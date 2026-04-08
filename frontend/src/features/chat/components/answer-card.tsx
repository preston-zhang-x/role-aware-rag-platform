import { AlertCircle, Bot, FileText, LoaderCircle } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AnswerMarkdown } from "@/features/chat/components/answer-markdown"
import { AnswerMetadata } from "@/features/chat/components/answer-metadata"
import type { ChatAssistantMessage } from "@/features/chat/types"

type AnswerCardProps = {
  message: ChatAssistantMessage
}

function renderSourceBadgeLabel(label: string, value: string | null | undefined) {
  if (!value) {
    return null
  }

  return (
    <Badge key={`${label}-${value}`} variant="outline" className="h-6 px-2.5 text-[11px]">
      {label}: {value}
    </Badge>
  )
}

export function AnswerCard({ message }: AnswerCardProps) {
  const isLoading = message.status === "loading"
  const isError = message.status === "error"
  const hasSources = message.sources.length > 0

  return (
    <div className="flex items-start gap-3">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <Bot className="size-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="rounded-[28px] rounded-tl-md border border-white/70 bg-white/95 p-5 shadow-[0_22px_44px_-32px_rgba(15,23,42,0.35)]">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-slate-900">AI アシスタント</span>
                {isLoading ? (
                  <Badge variant="secondary" className="gap-1.5">
                    <LoaderCircle className="size-3 animate-spin" />
                    回答を生成中
                  </Badge>
                ) : isError ? (
                  <Badge variant="destructive">応答エラー</Badge>
                ) : (
                  <Badge variant="outline">回答完了</Badge>
                )}
              </div>

              <p className="text-xs leading-5 text-slate-600">
                回答は現在の role で閲覧可能なドキュメントだけを対象に生成されます。
              </p>
            </div>
          </div>

          <div className="mt-4">
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-[92%]" />
                <Skeleton className="h-4 w-[85%]" />
                <Skeleton className="h-4 w-[68%]" />
              </div>
            ) : isError ? (
              <Alert variant="destructive">
                <AlertCircle className="size-4" />
                <AlertTitle>回答を取得できませんでした</AlertTitle>
                <AlertDescription>{message.errorMessage}</AlertDescription>
              </Alert>
            ) : (
              <AnswerMarkdown>{message.answer}</AnswerMarkdown>
            )}
          </div>

          {isLoading ? (
            <div className="mt-6 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <FileText className="size-4 text-primary" />
                参照ソースを整理しています
              </div>
              <div className="grid gap-3">
                <div className="rounded-2xl border bg-slate-50/70 p-4">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="mt-3 h-3 w-24" />
                  <Skeleton className="mt-4 h-3 w-full" />
                  <Skeleton className="mt-2 h-3 w-[92%]" />
                </div>
              </div>
            </div>
          ) : !isError ? (
            <div className="mt-6 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <FileText className="size-4 text-primary" />
                参照ソース
              </div>

              {hasSources ? (
                <div className="grid gap-3">
                  {message.sources.map((source) => (
                    <div
                      key={`${source.source_file}-${source.chunk_index}`}
                      className="rounded-2xl border bg-slate-50/80 p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <p className="font-medium text-slate-900">{source.source_file}</p>
                        <Badge variant="secondary" className="h-6 px-2.5 text-[11px]">
                          chunk {source.chunk_index}
                        </Badge>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        {renderSourceBadgeLabel("Sheet", source.sheet_name)}
                        {renderSourceBadgeLabel("Cell", source.cell_range)}
                        {renderSourceBadgeLabel("Type", source.content_type)}
                      </div>

                      <p className="mt-3 text-sm leading-6 whitespace-pre-wrap text-slate-700">
                        {source.text}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed bg-slate-50/70 p-4 text-sm leading-6 text-slate-600">
                  今回の回答では表示可能な参照ソースが返されませんでした。
                </div>
              )}
            </div>
          ) : null}

          <div className="mt-6">
            <AnswerMetadata metadata={message.metadata} isLoading={isLoading} />
          </div>
        </div>
      </div>
    </div>
  )
}
