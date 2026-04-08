import { useQueryClient } from "@tanstack/react-query"
import { useEffect, type PropsWithChildren } from "react"
import { Navigate, useLocation } from "react-router-dom"

import { AppShell } from "@/components/layout/app-shell"
import { PageHeader } from "@/components/layout/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useCurrentUser } from "@/features/auth/hooks/use-current-user"
import { clearAccessToken, hasAccessToken } from "@/lib/auth/token-storage"

export function AuthGuard({ children }: PropsWithChildren) {
  const location = useLocation()
  const queryClient = useQueryClient()
  const tokenExists = hasAccessToken()
  const currentUserQuery = useCurrentUser()

  useEffect(() => {
    if (currentUserQuery.isError) {
      clearAccessToken()
      queryClient.clear()
    }
  }, [currentUserQuery.isError, queryClient])

  if (!tokenExists) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (currentUserQuery.isPending) {
    return (
      <AppShell
        header={
          <PageHeader
            eyebrow="AUTH"
            title="認証状態を確認しています"
            description="保存済みトークンを使って現在のユーザー情報を取得しています。"
          />
        }
      >
        <Card className="border-white/70">
          <CardContent className="space-y-4 pt-4">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </CardContent>
        </Card>
      </AppShell>
    )
  }

  if (currentUserQuery.isError || !currentUserQuery.data) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <>{children}</>
}
