import { getAccessToken } from "@/lib/auth/token-storage"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ""

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE"

type RequestOptions<TBody> = {
  method?: HttpMethod
  body?: TBody
  headers?: HeadersInit
  auth?: boolean
  signal?: AbortSignal
}

type ValidationDetailItem = {
  msg?: string
}

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.data = data
  }
}

function buildRequestBody(body: unknown, headers: Headers) {
  if (body == null) {
    return undefined
  }

  if (body instanceof URLSearchParams) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/x-www-form-urlencoded")
    }
    return body.toString()
  }

  if (
    body instanceof FormData ||
    body instanceof Blob ||
    typeof body === "string" ||
    body instanceof ArrayBuffer
  ) {
    return body
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  return JSON.stringify(body)
}

function parseResponseText(text: string) {
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function getErrorMessage(data: unknown, fallback: string) {
  if (typeof data === "string" && data.trim() !== "") {
    return data
  }

  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail

    if (typeof detail === "string" && detail.trim() !== "") {
      return detail
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as ValidationDetailItem).msg ?? "")
          }
          return String(item)
        })
        .filter(Boolean)
        .join(" / ")
    }
  }

  return fallback
}

export async function http<TResponse, TBody = unknown>(
  path: string,
  options: RequestOptions<TBody> = {}
): Promise<TResponse> {
  const { method = "GET", body, headers: headersInit, auth = false, signal } = options
  const headers = new Headers(headersInit)

  if (auth) {
    const accessToken = getAccessToken()
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`)
    }
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: buildRequestBody(body, headers),
      signal,
    })

    const rawText = await response.text()
    const data = parseResponseText(rawText)

    if (!response.ok) {
      throw new ApiError(
        getErrorMessage(data, `Request failed with status ${response.status}`),
        response.status,
        data
      )
    }

    return data as TResponse
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }

    throw new ApiError("Network request failed", 0, null)
  }
}
