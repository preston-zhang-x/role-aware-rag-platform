import { useRef, useState } from "react"

import { useAskQuestion } from "@/features/chat/hooks/use-ask-question"
import type {
  ChatAssistantMessage,
  ChatMessage,
  ChatUserMessage,
} from "@/features/chat/types"
import { ApiError } from "@/lib/api/http"

function createMessageId(prefix: string) {
  const randomPart =
    globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2, 10)

  return `${prefix}-${randomPart}`
}

function createUserMessage(question: string): ChatUserMessage {
  return {
    id: createMessageId("user"),
    role: "user",
    question,
    createdAt: new Date().toISOString(),
  }
}

function createAssistantMessage(): ChatAssistantMessage {
  return {
    id: createMessageId("assistant"),
    role: "assistant",
    status: "loading",
    answer: "",
    sources: [],
    metadata: null,
    createdAt: new Date().toISOString(),
  }
}

function replaceAssistantMessage(
  messages: ChatMessage[],
  messageId: string,
  update: Partial<Pick<ChatAssistantMessage, "status" | "answer" | "sources" | "metadata" | "errorMessage">>
) {
  return messages.map((message) => {
    if (message.role !== "assistant" || message.id !== messageId) {
      return message
    }

    return {
      ...message,
      ...update,
    }
  })
}

function getAskErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return "API サーバーに接続できません。バックエンドが起動しているか確認してください。"
    }

    if (error.status === 401) {
      return "認証セッションの確認に失敗しました。再ログインしてからお試しください。"
    }

    return error.message
  }

  return "回答の取得に失敗しました。時間をおいて再試行してください。"
}

export function useChatSession() {
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const askQuestionMutation = useAskQuestion()
  const isSubmittingRef = useRef(false)

  async function submitQuestion(question: string) {
    const trimmedQuestion = question.trim()

    if (trimmedQuestion === "" || isSubmittingRef.current) {
      return
    }

    const userMessage = createUserMessage(trimmedQuestion)
    const assistantMessage = createAssistantMessage()

    isSubmittingRef.current = true
    setIsSubmitting(true)
    setMessages((current) => [...current, userMessage, assistantMessage])
    setDraft("")

    try {
      const response = await askQuestionMutation.mutateAsync({
        question: trimmedQuestion,
      })

      setMessages((current) =>
        replaceAssistantMessage(current, assistantMessage.id, {
          status: "success",
          answer: response.answer,
          sources: response.sources,
          metadata: response.metadata,
          errorMessage: undefined,
        })
      )
    } catch (error) {
      setMessages((current) =>
        replaceAssistantMessage(current, assistantMessage.id, {
          status: "error",
          answer: "",
          sources: [],
          metadata: null,
          errorMessage: getAskErrorMessage(error),
        })
      )
    } finally {
      isSubmittingRef.current = false
      setIsSubmitting(false)
    }
  }

  return {
    draft,
    setDraft,
    messages,
    isSubmitting,
    submitQuestion,
  }
}
