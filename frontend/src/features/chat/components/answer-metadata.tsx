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
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-2xl border bg-white/80 p-3.5">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-7 w-24" />
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
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon

        return (
          <div key={item.label} className="rounded-2xl border bg-white/80 p-3.5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {item.label}
                </p>
                <p className="mt-2.5 text-xl font-semibold tracking-tight text-slate-900">
                  {item.value}
                </p>
              </div>

              <div className="flex size-9 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Icon className="size-4" />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
