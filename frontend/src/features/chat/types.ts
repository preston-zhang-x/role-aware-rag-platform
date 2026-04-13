import type { operations } from "@/lib/api/generated/schema"

type AskQuestionOperation = operations["ask_api_v1_rag_ask_post"]

export const CHAT_QUESTION_MAX_LENGTH = 2000

export type AskQuestionRequest =
  AskQuestionOperation["requestBody"]["content"]["application/json"]

export type AskQuestionResponse =
  AskQuestionOperation["responses"][200]["content"]["application/json"]

export type AskQuestionSource = AskQuestionResponse["sources"][number]

export type AskQuestionMetadata = AskQuestionResponse["metadata"]

export type ChatUserMessage = {
  id: string
  role: "user"
  question: string
  createdAt: string
}

export type ChatAssistantMessageStatus = "loading" | "success" | "error"

export type ChatAssistantMessage = {
  id: string
  role: "assistant"
  status: ChatAssistantMessageStatus
  answer: string
  sources: AskQuestionSource[]
  metadata: AskQuestionMetadata | null
  errorMessage?: string
  createdAt: string
}

export type ChatMessage = ChatUserMessage | ChatAssistantMessage
