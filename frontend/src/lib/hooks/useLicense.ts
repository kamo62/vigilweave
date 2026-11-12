import { useQuery } from '@tanstack/react-query'

import { fetchCapabilities } from '@/lib/api'

export function useLicense() {
  const query = useQuery({
    queryKey: ['capabilities'],
    queryFn: fetchCapabilities,
    staleTime: 5 * 60 * 1000,
  })

  const license = query.data?.license
  const tier = typeof license?.tier === 'string' ? license.tier : 'community'
  const features = Array.isArray(license?.features)
    ? license.features.filter((feature): feature is string => typeof feature === 'string')
    : []
  const organization = typeof license?.organization === 'string' ? license.organization : null
  const distributionMode =
    typeof query.data?.runtime?.distribution_mode === 'string'
      ? query.data.runtime.distribution_mode
      : 'community'

  return {
    tier,
    features,
    organization,
    distributionMode,
    isCommunityDistribution: distributionMode === 'community',
    hasFeature: (feature: string) => {
      return features.includes(feature)
    },
    isLoading: query.isLoading,
  }
}
