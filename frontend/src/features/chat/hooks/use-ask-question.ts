import { useMutation } from "@tanstack/react-query"

import { askQuestion } from "@/features/chat/api/ask-question"
import type { AskQuestionRequest } from "@/features/chat/types"

export function useAskQuestion() {
  return useMutation({
    mutationKey: ["chat", "ask-question"],
    mutationFn: (payload: AskQuestionRequest) => askQuestion(payload),
  })
}
