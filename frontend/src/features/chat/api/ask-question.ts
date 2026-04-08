import type {
  AskQuestionRequest,
  AskQuestionResponse,
} from "@/features/chat/types"
import { http } from "@/lib/api/http"

export function askQuestion(
  payload: AskQuestionRequest
): Promise<AskQuestionResponse> {
  return http<AskQuestionResponse, AskQuestionRequest>("/api/v1/rag/ask", {
    method: "POST",
    body: payload,
    auth: true,
  })
}
