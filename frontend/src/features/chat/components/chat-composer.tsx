import { LoaderCircle, SendHorizonal } from "lucide-react"
import type { FormEvent, KeyboardEvent } from "react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

type ChatComposerProps = {
  value: string
  onChange: (value: string) => void
  onSubmit: (question: string) => Promise<void> | void
  isSubmitting: boolean
  maxLength: number
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  isSubmitting,
  maxLength,
}: ChatComposerProps) {
  const canSubmit = value.trim() !== "" && !isSubmitting

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!canSubmit) {
      return
    }

    void onSubmit(value)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return
    }

    event.preventDefault()

    if (!canSubmit) {
      return
    }

    void onSubmit(value)
  }

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-4">
      <div className="rounded-[28px] border border-white/70 bg-white/90 p-4 shadow-inner shadow-white/80">
        <Textarea
          value={value}
          maxLength={maxLength}
          placeholder="知りたいことを入力してください。例: 売上レポートの提出前チェック項目を箇条書きでまとめてください。"
          className="min-h-[128px] resize-none border-0 bg-transparent px-0 py-0 shadow-none focus-visible:border-transparent focus-visible:ring-0"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        <div className="mt-4 flex flex-col gap-3 border-t border-slate-200/80 pt-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>Enter で送信、Shift + Enter で改行できます。</p>
            <p>{value.length}/{maxLength}</p>
          </div>

          <Button type="submit" size="lg" disabled={!canSubmit}>
            {isSubmitting ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <SendHorizonal className="size-4" />
            )}
            {isSubmitting ? "送信中..." : "送信"}
          </Button>
        </div>
      </div>
    </form>
  )
}
