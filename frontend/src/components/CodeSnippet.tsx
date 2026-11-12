interface CodeLine {
  line: number
  text: string
}

interface CodeContext {
  start_line: number
  end_line: number
  issue_line: number
  lines: CodeLine[]
}

interface CodeSnippetProps {
  context: CodeContext
  message?: string
}

export function CodeSnippet({ context, message }: CodeSnippetProps) {
  const maxLineNum = context.end_line
  const gutterWidth = String(maxLineNum).length

  return (
    <div className="overflow-hidden rounded-sm border border-border bg-[hsl(var(--card))]">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[13px] leading-[1.6]">
          <tbody>
            {context.lines.map((entry) => {
              const isIssue = entry.line === context.issue_line
              return (
                <tr
                  key={entry.line}
                  className={isIssue ? 'bg-danger/10' : 'hover:bg-accent/30'}
                >
                  <td className="select-none border-r border-border px-3 text-right text-muted-foreground/50 align-top">
                    {String(entry.line).padStart(gutterWidth, '\u00A0')}
                  </td>
                  <td className="whitespace-pre px-4 align-top">
                    <span className={isIssue ? 'text-danger' : 'text-foreground/90'}>
                      {entry.text || '\u00A0'}
                    </span>
                  </td>
                </tr>
              )
            })}
            {message ? (
              <tr>
                <td className="border-r border-border px-3" />
                <td className="px-4 py-2">
                  <div className="inline-flex items-start gap-2 rounded-sm border border-danger/30 bg-danger/10 px-3 py-1.5 text-xs text-danger">
                    <svg
                      className="mt-0.5 h-3.5 w-3.5 shrink-0"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
                      />
                    </svg>
                    <span>{message}</span>
                  </div>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export type { CodeContext }
