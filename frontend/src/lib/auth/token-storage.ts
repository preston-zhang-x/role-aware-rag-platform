const ACCESS_TOKEN_STORAGE_KEY = "role-aware-rag-platform.access-token"

function getStorage() {
  if (typeof window === "undefined") {
    return null
  }

  return window.localStorage
}

export function getAccessToken() {
  return getStorage()?.getItem(ACCESS_TOKEN_STORAGE_KEY) ?? null
}

export function setAccessToken(accessToken: string) {
  getStorage()?.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)
}

export function clearAccessToken() {
  getStorage()?.removeItem(ACCESS_TOKEN_STORAGE_KEY)
}

export function hasAccessToken() {
  return Boolean(getAccessToken())
}
