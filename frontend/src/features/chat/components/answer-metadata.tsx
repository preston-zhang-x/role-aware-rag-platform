import { Bot, Coins, Gauge, Sigma } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import type { AskQuestionMetadata } from "@/features/chat/types"

type AnswerMetadataProps = {
  metadata: AskQuestionMetadata | null
  isLoading?: boolean
}

function formatLatency(latencyMs: number) {
  if (latencyMs >= 1000) {
    const seconds = latencyMs / 1000
    return `${seconds.toFixed(seconds >= 10 ? 0 : 1)}s`
  }

  return `${Math.round(latencyMs)}ms`
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("ja-JP").format(value)
}

function getDisplayLatency(metadata: AskQuestionMetadata) {
  return metadata.display_latency_ms ?? metadata.latency_ms
}

export function AnswerMetadata({ metadata, isLoading = false }: AnswerMetadataProps) {
  if (isLoading) {
    return (
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="rounded-xl border border-slate-200/70 bg-slate-50/45 px-3 py-2.5"
          >
            <Skeleton className="h-2.5 w-20" />
            <Skeleton className="mt-2 h-5 w-20" />
          </div>
        ))}
      </div>
    )
  }

  if (!metadata) {
    return null
  }

  const items = [
    {
      label: "Latency",
      value: formatLatency(getDisplayLatency(metadata)),
      icon: Gauge,
    },
    {
      label: "Prompt Tokens",
      value: formatNumber(metadata.prompt_tokens),
      icon: Coins,
    },
    {
      label: "Completion Tokens",
      value: formatNumber(metadata.completion_tokens),
      icon: Bot,
    },
    {
      label: "Total Tokens",
      value: formatNumber(metadata.total_tokens),
      icon: Sigma,
    },
  ]

  return (
    <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon

        return (
          <div
            key={item.label}
            className="rounded-xl border border-slate-200/70 bg-slate-50/45 px-3 py-2.5"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                  {item.label}
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-700">
                  {item.value}
                </p>
              </div>

              <div className="flex size-7 items-center justify-center rounded-xl bg-white/80 text-slate-400">
                <Icon className="size-3.5" />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
