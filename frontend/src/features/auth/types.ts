import type { CurrentUserResponse, LoginResponse, UserRole } from "@/lib/api/types"

export type AuthSession = LoginResponse
export type AuthUser = CurrentUserResponse

export type LoginCredentials = {
  username: string
  password: string
}

export const roleLabelMap: Record<UserRole, string> = {
  admin: "ADMIN",
  manager: "MANAGER",
  staff: "STAFF",
}
