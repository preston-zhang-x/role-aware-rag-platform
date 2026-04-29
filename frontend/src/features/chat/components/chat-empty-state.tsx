import { Compass, ShieldCheck, Sparkles } from "lucide-react"


type ChatEmptyStateProps = {
  roleLabel: string
}

export function ChatEmptyState({ roleLabel }: ChatEmptyStateProps) {
  return (
    <div className="mx-auto max-w-3xl rounded-[32px] border border-dashed border-slate-300/80 bg-white/75 p-8 text-center shadow-[0_30px_80px_-48px_rgba(15,23,42,0.35)]">
      <div className="mx-auto flex size-14 items-center justify-center rounded-3xl bg-primary/10 text-primary">
        <Sparkles className="size-6" />
      </div>

      <div className="mt-5 space-y-3">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
          RAG チャットを始めましょう
        </h2>
      </div>

      <div className="mt-6 grid gap-3 text-left md:grid-cols-3">
        <div className="rounded-2xl border bg-white/80 p-4">
          <ShieldCheck className="size-5 text-primary" />
          <p className="mt-3 text-sm font-semibold text-slate-900">Role Filter</p>
          <p className="mt-2 text-xs leading-5 text-slate-600">
            回答は現在の role で参照可能な文書に限定されます。
          </p>
        </div>

        <div className="rounded-2xl border bg-white/80 p-4">
          <Compass className="size-5 text-primary" />
          <p className="mt-3 text-sm font-semibold text-slate-900">Suggested Prompt</p>
          <p className="mt-2 text-xs leading-5 text-slate-600">
            手順、定義、チェック項目、該当資料の確認などの質問が向いています。
          </p>
        </div>

        <div className="rounded-2xl border bg-white/80 p-4">
          <Sparkles className="size-5 text-primary" />
          <p className="mt-3 text-sm font-semibold text-slate-900">Traceable Answer</p>
          <p className="mt-2 text-xs leading-5 text-slate-600">
            回答本文だけでなく、参照したファイルや処理メタデータも確認できます。
          </p>
        </div>
      </div>
    </div>
  )
}
