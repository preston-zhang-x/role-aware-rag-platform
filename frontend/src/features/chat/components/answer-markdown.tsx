import ReactMarkdown from "react-markdown"

import { cn } from "@/lib/utils"

type AnswerMarkdownProps = {
  children: string
}

export function AnswerMarkdown({ children }: AnswerMarkdownProps) {
  return (
    <div className="text-sm text-slate-700">
      <ReactMarkdown
        components={{
          p: ({ className, ...props }) => (
            <p
              className={cn(
                "leading-7 text-slate-700 [&:not(:first-child)]:mt-4",
                className
              )}
              {...props}
            />
          ),
          ol: ({ className, ...props }) => (
            <ol
              className={cn(
                "mt-4 list-decimal space-y-2 pl-5 leading-7 text-slate-700",
                className
              )}
              {...props}
            />
          ),
          ul: ({ className, ...props }) => (
            <ul
              className={cn(
                "mt-4 list-disc space-y-2 pl-5 leading-7 text-slate-700",
                className
              )}
              {...props}
            />
          ),
          li: ({ className, ...props }) => (
            <li className={cn("pl-1", className)} {...props} />
          ),
          strong: ({ className, ...props }) => (
            <strong className={cn("font-semibold text-slate-900", className)} {...props} />
          ),
          a: ({ className, ...props }) => (
            <a
              className={cn(
                "font-medium text-primary underline underline-offset-4 hover:text-primary/80",
                className
              )}
              target="_blank"
              rel="noreferrer"
              {...props}
            />
          ),
          blockquote: ({ className, ...props }) => (
            <blockquote
              className={cn(
                "mt-4 border-l-2 border-primary/25 bg-slate-50/80 px-4 py-3 text-slate-700",
                className
              )}
              {...props}
            />
          ),
          code: ({ className, children: codeChildren, ...props }) => {
            const content = String(codeChildren)
            const isBlock = Boolean(className) || content.includes("\n")

            if (isBlock) {
              return (
                <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950 px-4 py-3 text-xs leading-6 text-slate-100">
                  <code className={className} {...props}>
                    {content.replace(/\n$/, "")}
                  </code>
                </pre>
              )
            }

            return (
              <code
                className={cn(
                  "rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-slate-900",
                  className
                )}
                {...props}
              >
                {content}
              </code>
            )
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
