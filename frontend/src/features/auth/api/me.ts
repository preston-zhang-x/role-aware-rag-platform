import type { AuthUser } from "@/features/auth/types"
import { http } from "@/lib/api/http"

export async function getCurrentUser(): Promise<AuthUser> {
  return http<AuthUser>("/api/v1/auth/me", {
    auth: true,
  })
}
