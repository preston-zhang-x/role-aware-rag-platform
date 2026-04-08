import type { AuthSession, LoginCredentials } from "@/features/auth/types"
import { http } from "@/lib/api/http"

export async function login(credentials: LoginCredentials): Promise<AuthSession> {
  const body = new URLSearchParams()
  body.set("username", credentials.username)
  body.set("password", credentials.password)

  return http<AuthSession, URLSearchParams>("/api/v1/auth/login", {
    method: "POST",
    body,
  })
}
