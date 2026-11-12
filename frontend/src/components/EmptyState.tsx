import { Inbox } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'

type EmptyStateProps = {
  title: string
  body: string
}

export function EmptyState({ title, body }: EmptyStateProps) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <Inbox className="text-muted-foreground" size={18} />
        </div>
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <p className="max-w-md text-sm text-muted-foreground">{body}</p>
      </CardContent>
    </Card>
  )
}
