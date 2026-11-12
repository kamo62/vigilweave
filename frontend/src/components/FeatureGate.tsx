import type { ReactNode } from 'react'

import { Lock } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useLicense } from '@/lib/hooks/useLicense'

interface FeatureGateProps {
  feature: string
  children: ReactNode
  fallback?: ReactNode
}

export function FeatureGate({ feature, children, fallback }: FeatureGateProps) {
  const { hasFeature, isCommunityDistribution, tier } = useLicense()

  if (hasFeature(feature)) {
    return <>{children}</>
  }

  if (fallback) {
    return <>{fallback}</>
  }

  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
        <Lock className="text-muted-foreground" size={28} />
        <div>
          <p className="text-sm font-medium">
            {isCommunityDistribution
              ? 'This feature is not available in the Community edition'
              : 'This feature requires a higher-tier license'}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {isCommunityDistribution ? (
              'Commercial features are only available through a separate commercial distribution.'
            ) : (
              <>
                You are currently on the <span className="font-semibold capitalize">{tier}</span> plan.
              </>
            )}
          </p>
        </div>
        {isCommunityDistribution ? null : (
          <Button asChild size="sm" variant="default">
            <a href="https://vigilweave.com/pricing" rel="noopener noreferrer" target="_blank">
              Upgrade
            </a>
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
