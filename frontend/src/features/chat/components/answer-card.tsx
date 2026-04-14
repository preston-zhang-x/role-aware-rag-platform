import { useState } from "react"
import {
  AlertCircle,
  Bot,
  ChevronDown,
  ChevronUp,
  FileText,
  LoaderCircle,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { AnswerMarkdown } from "@/features/chat/components/answer-markdown"
import { AnswerMetadata } from "@/features/chat/components/answer-metadata"
import type { AskQuestionSource, ChatAssistantMessage } from "@/features/chat/types"

type AnswerCardProps = {
  message: ChatAssistantMessage
}

const DEFAULT_VISIBLE_SOURCE_COUNT = 3
const SOURCE_PREVIEW_MAX_LINES = 2
const SOURCE_PREVIEW_MAX_CHARS = 120

type SourcePreview = {
  text: string
  isTruncated: boolean
}

function renderSourceBadgeLabel(label: string, value: string | null | undefined) {
  if (!value) {
    return null
  }

  return (
    <Badge
      key={`${label}-${value}`}
      variant="outline"
      className="h-auto max-w-full px-2.5 py-1 text-[11px] leading-4 whitespace-normal"
    >
      {label}: {value}
    </Badge>
  )
}

function buildSourcePreview(text: string): SourcePreview {
  const nonEmptyLines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

  if (nonEmptyLines.length === 0) {
    return {
      text: "",
      isTruncated: false,
    }
  }

  const limitedLines = nonEmptyLines.slice(0, SOURCE_PREVIEW_MAX_LINES)
  const combinedPreview = limitedLines.join("\n")
  const exceedsLineLimit = nonEmptyLines.length > SOURCE_PREVIEW_MAX_LINES
  const exceedsCharLimit = combinedPreview.length > SOURCE_PREVIEW_MAX_CHARS
  const previewText = exceedsCharLimit
    ? combinedPreview.slice(0, SOURCE_PREVIEW_MAX_CHARS).trimEnd()
    : combinedPreview
  const isTruncated = exceedsLineLimit || exceedsCharLimit

  return {
    text: isTruncated ? `${previewText}…` : previewText,
    isTruncated,
  }
}

type SourcePreviewCardProps = {
  source: AskQuestionSource
}

function SourcePreviewCard({ source }: SourcePreviewCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const preview = buildSourcePreview(source.text)
  const displayText = isExpanded || !preview.isTruncated ? source.text : preview.text

  return (
    <div className="rounded-2xl border bg-slate-50/55 p-3.5">
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <p className="break-all text-sm font-medium text-slate-900">
            {source.source_file}
          </p>

          <div className="mt-2 flex flex-wrap gap-2">
            {renderSourceBadgeLabel("Sheet", source.sheet_name)}
            {renderSourceBadgeLabel("Cell", source.cell_range)}
            {renderSourceBadgeLabel("Type", source.content_type)}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge variant="secondary" className="h-6 px-2.5 text-[11px]">
            chunk {source.chunk_index}
          </Badge>

          {preview.isTruncated ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-expanded={isExpanded}
              className="rounded-full px-3 text-[11px] text-slate-700"
              onClick={() => setIsExpanded((current) => !current)}
            >
              {isExpanded ? "折りたたむ" : "全文"}
              {isExpanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </Button>
          ) : null}
        </div>
      </div>

      {displayText ? (
        <p className="mt-2.5 text-xs leading-5 whitespace-pre-wrap text-slate-600">
          {displayText}
        </p>
      ) : null}
    </div>
  )
}

export function AnswerCard({ message }: AnswerCardProps) {
  const [areSourcesExpanded, setAreSourcesExpanded] = useState(false)
  const [areAllSourcesVisible, setAreAllSourcesVisible] = useState(false)
  const isLoading = message.status === "loading"
  const isError = message.status === "error"
  const hasSources = message.sources.length > 0
  const hasHiddenSources = message.sources.length > DEFAULT_VISIBLE_SOURCE_COUNT
  const hiddenSourceCount = Math.max(
    0,
    message.sources.length - DEFAULT_VISIBLE_SOURCE_COUNT
  )
  const visibleSources = areAllSourcesVisible
    ? message.sources
    : message.sources.slice(0, DEFAULT_VISIBLE_SOURCE_COUNT)

  function toggleSourcesSection() {
    setAreSourcesExpanded((current) => {
      if (current) {
        setAreAllSourcesVisible(false)
      }

      return !current
    })
  }

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
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/55 px-3.5 py-3">
                <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                  <FileText className="size-4 text-primary" />
                  <span>参照ソース</span>
                  {hasSources ? (
                    <Badge variant="secondary" className="h-6 px-2.5 text-[11px]">
                      {message.sources.length} 件
                    </Badge>
                  ) : null}
                </div>

                {hasSources ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-expanded={areSourcesExpanded}
                    className="rounded-full px-3 text-xs text-slate-600"
                    onClick={toggleSourcesSection}
                  >
                    {areSourcesExpanded ? "参照ソースを隠す" : "参照ソースを表示"}
                    {areSourcesExpanded ? (
                      <ChevronUp className="size-3.5" />
                    ) : (
                      <ChevronDown className="size-3.5" />
                    )}
                  </Button>
                ) : null}
              </div>

              {hasSources ? (
                areSourcesExpanded ? (
                  <div className="space-y-3">
                    <div className="grid gap-3">
                      {visibleSources.map((source, index) => (
                        <SourcePreviewCard
                          key={`${source.source_file}-${source.chunk_index}-${index}`}
                          source={source}
                        />
                      ))}
                    </div>

                    {hasHiddenSources ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-auto rounded-full px-3 py-2 text-xs text-slate-600"
                        onClick={() => setAreAllSourcesVisible((current) => !current)}
                      >
                        {areAllSourcesVisible ? "隠す" : `他 ${hiddenSourceCount} 件`}
                      </Button>
                    ) : null}
                  </div>
                ) : null
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
