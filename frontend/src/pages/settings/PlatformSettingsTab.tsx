import { useQuery } from '@tanstack/react-query'
import { Globe, Lock, Monitor, Server, Wrench } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { MetricCard } from '@/components/MetricCard'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { fetchCapabilities } from '@/lib/api'

export function PlatformSettingsTab() {
  const capabilitiesQuery = useQuery({
    queryKey: ['capabilities'],
    queryFn: fetchCapabilities,
  })
  const capabilities = capabilitiesQuery.data

  const languages = capabilities?.languages ?? []
  const scanTypes = capabilities?.scan_types ?? []
  const toolingProfiles = capabilities?.tooling_profiles ?? {}
  const hostRequirements = capabilities?.host_requirements ?? {}
  const runtime = capabilities?.runtime ?? {}

  if (capabilitiesQuery.isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner label="Loading capabilities..." />
      </div>
    )
  }

  if (capabilitiesQuery.isError) {
    return (
      <EmptyState
        body="Could not reach the backend. Make sure the API server is running."
        title="Connection failed"
      />
    )
  }

  if (!capabilities) {
    return <EmptyState body="Capabilities are not available from the backend." title="No settings data" />
  }

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          detail={String(runtime.profile ?? 'unknown')}
          icon={<Server size={16} />}
          label="Profile"
          value={String(runtime.profile ?? 'N/A')}
        />
        <MetricCard
          detail="Supported platforms"
          icon={<Monitor size={16} />}
          label="Platforms"
          value={
            Array.isArray(runtime.platforms) ? String(runtime.platforms.length) : '0'
          }
        />
        <MetricCard
          detail="Configured scan types"
          icon={<Wrench size={16} />}
          label="Scan Types"
          value={String(scanTypes.length)}
        />
        <MetricCard
          detail="Detected languages"
          icon={<Globe size={16} />}
          label="Languages"
          value={String(languages.length)}
        />
      </div>

      {/* Server Profile */}
      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Runtime
            </p>
            <h2 className="text-lg font-semibold">Server profile</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="grid gap-3 p-6 sm:grid-cols-3">
          <Card className="bg-muted/50">
            <CardContent className="gap-1 p-4">
              <div className="flex items-center gap-2">
                <Server size={14} />
                <p className="text-sm font-semibold">Profile</p>
              </div>
              <p className="font-mono text-xs text-muted-foreground">
                {String(runtime.profile ?? 'unknown')}
              </p>
            </CardContent>
          </Card>
          <Card className="bg-muted/50">
            <CardContent className="gap-1 p-4">
              <div className="flex items-center gap-2">
                <Wrench size={14} />
                <p className="text-sm font-semibold">Platforms</p>
              </div>
              <p className="font-mono text-xs text-muted-foreground">
                {Array.isArray(runtime.platforms)
                  ? (runtime.platforms as string[]).join(', ')
                  : 'unknown'}
              </p>
            </CardContent>
          </Card>
          <Card className="bg-muted/50">
            <CardContent className="gap-1 p-4">
              <div className="flex items-center gap-2">
                <Lock size={14} />
                <p className="text-sm font-semibold">Auth mode</p>
              </div>
              <p className="text-xs text-muted-foreground">
                {capabilities.authentication?.api_keys ? 'API key enforced' : 'Open bootstrap'}
              </p>
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      {/* Scan types & languages */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="px-6 pt-5">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                Analysis
              </p>
              <h2 className="text-lg font-semibold">Scan types</h2>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="p-6">
            <div className="flex flex-wrap gap-2">
              {scanTypes.map((st) => (
                <Badge color="primary" key={st} variant="flat">
                  {st}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="px-6 pt-5">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                Detection
              </p>
              <h2 className="text-lg font-semibold">Supported languages</h2>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="p-6">
            <div className="flex flex-wrap gap-2">
              {languages.map((lang) => (
                <Badge key={lang} variant="flat">
                  {lang}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tooling Profiles */}
      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Contracts
            </p>
            <h2 className="text-lg font-semibold">Tooling profiles</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {Object.keys(toolingProfiles).length === 0 ? (
            <EmptyState body="No tooling profiles configured." title="No profiles" />
          ) : (
            Object.entries(toolingProfiles).map(([profile, tools]) => (
              <Card className="bg-muted/50" key={profile}>
                <CardContent className="gap-2 p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">{profile}</p>
                    <Badge variant="flat">
                      {tools.length} tools
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {tools.map((tool) => (
                      <Badge key={`${profile}-${tool}`} variant="flat">
                        {tool}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </CardContent>
      </Card>

      {/* Host Requirements */}
      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Host Requirements
            </p>
            <h2 className="text-lg font-semibold">Tool dependencies</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {Object.keys(hostRequirements).length === 0 ? (
            <EmptyState body="No special host requirements." title="No dependencies" />
          ) : (
            Object.entries(hostRequirements).map(([tool, description]) => (
              <Card className="bg-muted/50" key={tool}>
                <CardContent className="gap-1 p-4">
                  <p className="font-mono text-xs font-semibold">{tool}</p>
                  <p className="text-sm text-muted-foreground">{String(description)}</p>
                </CardContent>
              </Card>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
