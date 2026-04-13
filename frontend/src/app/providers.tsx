import { QueryClientProvider } from "@tanstack/react-query"
import type { PropsWithChildren } from "react"

import { queryClient } from "@/app/query-client"

export function AppProviders({ children }: PropsWithChildren) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
