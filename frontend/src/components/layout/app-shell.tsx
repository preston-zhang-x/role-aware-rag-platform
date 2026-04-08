import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type AppShellProps = {
  header?: ReactNode
  children: ReactNode
  className?: string
}

export function AppShell({ header, children, className }: AppShellProps) {
  return (
    <div className="relative min-h-screen overflow-hidden text-foreground">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8rem] top-[-6rem] h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute right-[-6rem] top-20 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        {header}
        <main className={cn("mt-6 flex-1", className)}>{children}</main>
      </div>
    </div>
  )
}
