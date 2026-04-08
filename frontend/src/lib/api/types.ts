import type { components, operations } from "@/lib/api/generated/schema"

export type ApiSchemas = components["schemas"]

export type UserRole = ApiSchemas["UserRole"]

export type LoginOperation = operations["login_api_v1_auth_login_post"]
export type MeOperation = operations["read_me_api_v1_auth_me_get"]

export type LoginRequest =
  LoginOperation["requestBody"]["content"]["application/x-www-form-urlencoded"]

export type LoginResponse =
  LoginOperation["responses"][200]["content"]["application/json"]

export type CurrentUserResponse =
  MeOperation["responses"][200]["content"]["application/json"]

export type ValidationErrorResponse = ApiSchemas["HTTPValidationError"]
