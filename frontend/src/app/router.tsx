import { Navigate, createBrowserRouter } from "react-router-dom"

import { AuthGuard } from "@/features/auth/components/auth-guard"
import LoginPage from "@/features/auth/pages/login-page"
import ChatPage from "@/features/chat/pages/chat-page"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/login" replace />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/chat",
    element: (
      <AuthGuard>
        <ChatPage />
      </AuthGuard>
    ),
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  },
])
