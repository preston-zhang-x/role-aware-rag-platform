import { useEffect, useRef } from "react"

import { ChatEmptyState } from "@/features/chat/components/chat-empty-state"
import { AnswerCard } from "@/features/chat/components/answer-card"
import type { ChatMessage } from "@/features/chat/types"

type ChatMessageListProps = {
  messages: ChatMessage[]
  roleLabel: string
}

export function ChatMessageList({ messages, roleLabel }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      block: "end",
      behavior: messages.length > 2 ? "smooth" : "auto",
    })
  }, [messages])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      {messages.length === 0 ? (
        <div className="flex min-h-[28rem] items-center justify-center py-8">
          <ChatEmptyState roleLabel={roleLabel} />
        </div>
      ) : (
        <div className="space-y-6 pb-4">
          {messages.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="flex justify-end">
                <div className="max-w-[90%] space-y-2 sm:max-w-[82%]">
                  <div className="flex items-center justify-end gap-2 text-xs text-slate-500">
                    <span>あなた</span>
                    <span className="flex size-8 items-center justify-center rounded-2xl bg-slate-900 text-[11px] font-semibold tracking-[0.12em] text-white">
                      YOU
                    </span>
                  </div>

                  <div className="rounded-[26px] rounded-tr-md bg-slate-900 px-5 py-4 text-sm leading-7 whitespace-pre-wrap text-white shadow-[0_22px_44px_-32px_rgba(15,23,42,0.9)]">
                    {message.question}
                  </div>
                </div>
              </div>
            ) : (
              <AnswerCard key={message.id} message={message} />
            )
          )}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
