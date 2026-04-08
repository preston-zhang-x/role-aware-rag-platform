import { ShieldCheck } from "lucide-react"

import { AppShell } from "@/components/layout/app-shell"
import { UserMenu } from "@/components/layout/user-menu"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useCurrentUser } from "@/features/auth/hooks/use-current-user"
import { roleLabelMap } from "@/features/auth/types"
import { ChatComposer } from "@/features/chat/components/chat-composer"
import { ChatMessageList } from "@/features/chat/components/chat-message-list"
import { useChatSession } from "@/features/chat/hooks/use-chat-session"
import { CHAT_QUESTION_MAX_LENGTH } from "@/features/chat/types"

export default function ChatPage() {
  const { data: currentUser } = useCurrentUser()
  const { draft, setDraft, messages, isSubmitting, submitQuestion } = useChatSession()
  const roleLabel = currentUser ? roleLabelMap[currentUser.role] : "ROLE"

  return (
    <AppShell
      className="min-h-0"
      header={
        <header className="flex flex-col gap-4 rounded-3xl border border-white/70 bg-white/75 p-5 shadow-[0_20px_60px_-30px_rgba(15,23,42,0.35)] backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              CHAT
            </p>
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
                Role Aware RAG Platform
              </h1>
              <p className="max-w-3xl text-sm leading-6 text-slate-600 sm:text-base">
                役割ごとに閲覧可能な社内文書を絞り込み、回答と根拠を 1 つのチャット画面で確認できます。
              </p>
            </div>
          </div>

          <UserMenu />
        </header>
      }
    >
      <Card className="flex min-h-0 flex-1 border-white/70 bg-white/80 backdrop-blur">
        <CardHeader className="border-b border-border/70">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <Badge variant="secondary" className="w-fit">
                RAG Chat
              </Badge>
              <CardTitle className="text-lg text-slate-900">
                質問、回答、参照情報をそのまま確認できる問い合わせビュー
              </CardTitle>
              <p className="max-w-3xl text-sm leading-6 text-slate-600">
                質問を送ると、回答本文に加えて参照ソースと応答メタデータを同じカード内に表示します。
              </p>
            </div>

            <div className="flex max-w-xl items-start gap-3 rounded-2xl border bg-slate-50/85 px-4 py-3 text-sm shadow-sm">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <ShieldCheck className="size-5" />
              </div>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Role Filter
                  </p>
                  <Badge variant="outline" className="h-6 px-2.5 text-[11px]">
                    現在の role: {roleLabel}
                  </Badge>
                </div>
                <p className="text-sm leading-6 text-slate-700">
                  回答は現在の role で閲覧可能なドキュメントに限定されます。
                </p>
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent className="flex min-h-0 flex-1 flex-col pt-4">
          <ChatMessageList messages={messages} roleLabel={roleLabel} />
        </CardContent>

        <CardFooter className="shrink-0 border-white/70 bg-slate-50/80">
          <ChatComposer
            value={draft}
            onChange={setDraft}
            onSubmit={submitQuestion}
            isSubmitting={isSubmitting}
            maxLength={CHAT_QUESTION_MAX_LENGTH}
          />
        </CardFooter>
      </Card>
    </AppShell>
  )
}
