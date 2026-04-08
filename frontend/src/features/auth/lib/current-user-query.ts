import { queryOptions } from "@tanstack/react-query"

import { getCurrentUser } from "@/features/auth/api/me"

export const currentUserQueryKey = ["auth", "current-user"] as const

export function currentUserQueryOptions() {
  return queryOptions({
    queryKey: currentUserQueryKey,
    queryFn: getCurrentUser,
    retry: false,
  })
}
