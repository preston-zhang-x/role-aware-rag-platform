import { useMutation, useQueryClient } from "@tanstack/react-query"

import { login } from "@/features/auth/api/login"
import {
  currentUserQueryKey,
  currentUserQueryOptions,
} from "@/features/auth/lib/current-user-query"
import type { LoginCredentials } from "@/features/auth/types"
import { clearAccessToken, setAccessToken } from "@/lib/auth/token-storage"

export function useLogin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationKey: ["auth", "login"],
    mutationFn: async (credentials: LoginCredentials) => {
      const session = await login(credentials)
      setAccessToken(session.access_token)
      queryClient.removeQueries({ queryKey: currentUserQueryKey })

      try {
        const currentUser = await queryClient.fetchQuery(currentUserQueryOptions())
        return { session, currentUser }
      } catch (error) {
        clearAccessToken()
        queryClient.removeQueries({ queryKey: currentUserQueryKey })
        throw error
      }
    },
    onError: () => {
      clearAccessToken()
      queryClient.removeQueries({ queryKey: currentUserQueryKey })
    },
  })
}
