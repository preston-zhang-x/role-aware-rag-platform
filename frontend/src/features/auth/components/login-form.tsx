import { AlertCircle, ArrowRight } from "lucide-react"
import { useState, type FormEvent } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useLogin } from "@/features/auth/hooks/use-login"
import type { LoginCredentials } from "@/features/auth/types"
import { ApiError } from "@/lib/api/http"

const EMPTY_CREDENTIALS: LoginCredentials = {
  username: "",
  password: "",
}

type RedirectState = {
  from?: {
    pathname: string
    search?: string
    hash?: string
  }
}

function getLoginErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return "API サーバーに接続できません。FastAPI が起動しているか確認してください。"
    }

    if (error.status === 401) {
      return "ユーザー名またはパスワードが正しくありません。"
    }

    return error.message
  }

  return "ログインに失敗しました。時間をおいて再試行してください。"
}

function getRedirectPath(state: RedirectState | null) {
  const from = state?.from

  if (!from) {
    return "/chat"
  }

  return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`
}

export function LoginForm() {
  const [credentials, setCredentials] = useState<LoginCredentials>(EMPTY_CREDENTIALS)

  const navigate = useNavigate()
  const location = useLocation()
  const loginMutation = useLogin()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    await loginMutation.mutateAsync({
      username: credentials.username.trim(),
      password: credentials.password,
    })

    navigate(getRedirectPath(location.state as RedirectState | null), {
      replace: true,
    })
  }

  return (
    <Card className="border-white/70">
      <CardHeader className="space-y-3">
        <Badge variant="secondary" className="w-fit">
          Sign In
        </Badge>
        <CardTitle className="text-2xl">ログイン</CardTitle>
        <CardDescription>
          データベースに登録済みのユーザー名とパスワードを入力してください。
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label htmlFor="username" className="text-sm font-medium text-slate-700">
              ユーザー名
            </label>
            <Input
              id="username"
              autoComplete="username"
              placeholder="your username"
              value={credentials.username}
              onChange={(event) =>
                setCredentials((current) => ({
                  ...current,
                  username: event.target.value,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium text-slate-700">
              パスワード
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={credentials.password}
              onChange={(event) =>
                setCredentials((current) => ({
                  ...current,
                  password: event.target.value,
                }))
              }
            />
          </div>

          {loginMutation.isError ? (
            <Alert variant="destructive">
              <AlertCircle className="size-4" />
              <AlertTitle>ログインできませんでした</AlertTitle>
              <AlertDescription>{getLoginErrorMessage(loginMutation.error)}</AlertDescription>
            </Alert>
          ) : null}

          <Button
            type="submit"
            className="w-full"
            disabled={
              loginMutation.isPending ||
              credentials.username.trim() === "" ||
              credentials.password.trim() === ""
            }
          >
            {loginMutation.isPending ? "ログイン中..." : "ワークスペースへ進む"}
            <ArrowRight className="size-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
