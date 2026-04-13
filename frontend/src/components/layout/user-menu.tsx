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
    <div className="flex max-w-full items-center gap-3 rounded-2xl border border-white/70 bg-white/92 px-3 py-2 shadow-[0_18px_36px_-24px_rgba(15,23,42,0.25)] backdrop-blur">
      <div className="min-w-0 flex flex-1 flex-wrap items-center gap-2">
        <p className="truncate text-sm font-semibold text-slate-900">
          {currentUser.username}
        </p>
        <Badge
          variant={roleBadgeVariantMap[currentUser.role]}
          className="h-6 px-2.5 text-[11px] tracking-[0.08em]"
        >
          {roleLabelMap[currentUser.role]}
        </Badge>
      </div>

      <div className="h-8 w-px shrink-0 bg-slate-200" />

      <Button
        type="button"
        variant="outline"
        size="sm"
        className="shrink-0"
        onClick={handleLogout}
      >
        <LogOut className="size-4" />
        ログアウト
      </Button>
    </div>
  )
}
