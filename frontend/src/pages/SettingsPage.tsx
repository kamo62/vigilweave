import { useEffect } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { CreditCard, Gauge, GitBranch, Key, Layers, Server, ShieldCheck, SlidersHorizontal, Users } from 'lucide-react'

import { FeatureGate } from '@/components/FeatureGate'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useLicense } from '@/lib/hooks/useLicense'
import { useAuth } from '@/lib/useAuth'
import { ApiKeysTab } from './settings/ApiKeysTab'
import { BillingTab } from './settings/BillingTab'
import { ConnectionsTab } from './settings/ConnectionsTab'
import { MonitoringTab } from './settings/MonitoringTab'
import { PlatformSettingsTab } from './settings/PlatformSettingsTab'
import { PortfoliosTab } from './settings/PortfoliosTab'
import { SaaSAdminTab } from './settings/SaaSAdminTab'
import { ToolingTab } from './settings/ToolingTab'
import { UsersTab } from './settings/UsersTab'

export function SettingsPage() {
  const { user } = useAuth()
  const { isCommunityDistribution } = useLicense()
  const navigate = useNavigate()
  const search = useSearch({ from: '/settings' })
  const isAdmin = user?.role === 'admin'
  const showSaaSAdmin = user?.platform_role === 'operator'
  const isOperatorOnly = showSaaSAdmin && !isAdmin
  const showBilling = !isCommunityDistribution
  const showAdminTabs = isAdmin
  const allowedTabs = isOperatorOnly
    ? ['saas-admin', 'platform']
    : [
        'platform',
        ...(showAdminTabs ? ['users', 'api-keys'] : []),
        ...(showBilling && showAdminTabs ? ['billing'] : []),
        ...(showAdminTabs ? ['connections', 'tooling', 'monitoring', 'portfolios'] : []),
        ...(showSaaSAdmin ? ['saas-admin'] : []),
      ]
  const activeTab = allowedTabs.includes(search.tab ?? '') ? (search.tab as string) : allowedTabs[0]

  useEffect(() => {
    if (search.tab === activeTab) {
      return
    }
    void navigate({
      to: '/settings',
      search: { tab: activeTab },
      replace: true,
    })
  }, [activeTab, navigate, search.tab])

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          {isOperatorOnly ? 'Hosted SaaS' : 'Administration'}
        </p>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isOperatorOnly
            ? 'Hosted tenant plans, platform operator access, and shared runtime visibility.'
            : 'Platform configuration, authentication, tool governance, monitoring, and portfolio management.'}
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={(tab) => void navigate({ to: '/settings', search: { tab } })}>
        <TabsList>
          <TabsTrigger value="platform">
            <div className="flex items-center gap-2">
              <Server size={14} />
              <span>Platform</span>
            </div>
          </TabsTrigger>
          {showAdminTabs ? (
            <TabsTrigger value="users">
              <div className="flex items-center gap-2">
                <Users size={14} />
                <span>Users</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showAdminTabs ? (
            <TabsTrigger value="api-keys">
              <div className="flex items-center gap-2">
                <Key size={14} />
                <span>API Keys</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showBilling && showAdminTabs ? (
            <TabsTrigger value="billing">
              <div className="flex items-center gap-2">
                <CreditCard size={14} />
                <span>Billing</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showAdminTabs ? (
            <TabsTrigger value="connections">
              <div className="flex items-center gap-2">
                <GitBranch size={14} />
                <span>Connections</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showAdminTabs ? (
            <TabsTrigger value="tooling">
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={14} />
                <span>Tooling</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showAdminTabs ? (
            <TabsTrigger value="monitoring">
              <div className="flex items-center gap-2">
                <Gauge size={14} />
                <span>Monitoring</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showAdminTabs ? (
            <TabsTrigger value="portfolios">
              <div className="flex items-center gap-2">
                <Layers size={14} />
                <span>Portfolios</span>
              </div>
            </TabsTrigger>
          ) : null}
          {showSaaSAdmin ? (
            <TabsTrigger value="saas-admin">
              <div className="flex items-center gap-2">
                <ShieldCheck size={14} />
                <span>Cloud</span>
              </div>
            </TabsTrigger>
          ) : null}
        </TabsList>
        <TabsContent value="platform">
          <div className="pt-4">
            <PlatformSettingsTab />
          </div>
        </TabsContent>
        {showAdminTabs ? (
          <TabsContent value="users">
            <div className="pt-4">
              <UsersTab />
            </div>
          </TabsContent>
        ) : null}
        {showAdminTabs ? (
          <TabsContent value="api-keys">
            <div className="pt-4">
              <ApiKeysTab />
            </div>
          </TabsContent>
        ) : null}
        {showBilling && showAdminTabs ? (
          <TabsContent value="billing">
            <div className="pt-4">
              <BillingTab />
            </div>
          </TabsContent>
        ) : null}
        {showAdminTabs ? (
          <TabsContent value="connections">
            <div className="pt-4">
              <ConnectionsTab />
            </div>
          </TabsContent>
        ) : null}
        {showAdminTabs ? (
          <TabsContent value="tooling">
            <div className="pt-4">
              <ToolingTab />
            </div>
          </TabsContent>
        ) : null}
        {showAdminTabs ? (
          <TabsContent value="monitoring">
            <div className="pt-4">
              <MonitoringTab />
            </div>
          </TabsContent>
        ) : null}
        {showAdminTabs ? (
          <TabsContent value="portfolios">
            <FeatureGate feature="portfolios">
              <div className="pt-4">
                <PortfoliosTab />
              </div>
            </FeatureGate>
          </TabsContent>
        ) : null}
        {showSaaSAdmin ? (
          <TabsContent value="saas-admin">
            <div className="pt-4">
              <SaaSAdminTab />
            </div>
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  )
}
