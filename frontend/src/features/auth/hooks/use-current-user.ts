import { useQuery } from "@tanstack/react-query"

import {
  currentUserQueryOptions,
} from "@/features/auth/lib/current-user-query"
import { hasAccessToken } from "@/lib/auth/token-storage"

export function useCurrentUser() {
  return useQuery({
    ...currentUserQueryOptions(),
    enabled: hasAccessToken(),
  })
}
