import { useQueryClient } from "@tanstack/react-query"
import { LogOut } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useCurrentUser } from "@/features/auth/hooks/use-current-user"
import { roleLabelMap } from "@/features/auth/types"
import { clearAccessToken } from "@/lib/auth/token-storage"

const roleBadgeVariantMap = {
  admin: "default",
  manager: "secondary",
  staff: "outline",
} as const

export function UserMenu() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: currentUser } = useCurrentUser()

  if (!currentUser) {
    return null
  }

  function handleLogout() {
    clearAccessToken()
    queryClient.clear()
    navigate("/login", { replace: true })
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-3 rounded-2xl border border-white/70 bg-white/85 px-3 py-2 shadow-sm">
      <div className="min-w-0 text-right">
        <p className="truncate text-sm font-semibold text-slate-900">
          {currentUser.username}
        </p>
        <div className="mt-1">
          <Badge variant={roleBadgeVariantMap[currentUser.role]}>
            {roleLabelMap[currentUser.role]}
          </Badge>
        </div>
      </div>

      <Button type="button" variant="outline" size="sm" onClick={handleLogout}>
        <LogOut className="size-4" />
        ログアウト
      </Button>
    </div>
  )
}
