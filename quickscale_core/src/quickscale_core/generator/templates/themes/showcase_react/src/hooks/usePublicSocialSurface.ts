import { useQuery } from '@tanstack/react-query'
import { ApiError, apiRequest } from '@/hooks/useApi'
import { useProjectConfig } from '@/hooks/useModules'

import type {
  PublicSocialSurface,
  SocialBasePayload,
  SocialEmbedRecord,
  SocialEmbedResolutionStatus,
  SocialEmbedsPayload,
  SocialLinkRecord,
  SocialLinkTreePayload,
  SocialPayloadStatus,
} from '@/quickscaleSeam.hooks'

// The social payload types live in the managed hook file; this hook re-exports
// them for the public pages, shell, and tests that import this module.
export type {
  PublicSocialSurface,
  SocialBasePayload,
  SocialEmbedRecord,
  SocialEmbedResolutionStatus,
  SocialEmbedsPayload,
  SocialLinkRecord,
  SocialLinkTreePayload,
  SocialPayloadStatus,
}

export interface PublicSocialNavigation {
  home: string
  linkTree: string
  embeds: string
}

type SocialPayloadBySurface = {
  link_tree: SocialLinkTreePayload
  embeds: SocialEmbedsPayload
}

const DEFAULT_NAVIGATION: PublicSocialNavigation = {
  home: '/',
  linkTree: '/social',
  embeds: '/social/embeds',
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isOptionalString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isOptionalNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function isSocialLinkRecord(value: unknown): value is SocialLinkRecord {
  if (value == null || typeof value !== 'object') {
    return false
  }

  const record = value as Record<string, unknown>
  return (
    typeof record.id === 'number' &&
    typeof record.title === 'string' &&
    typeof record.description === 'string' &&
    typeof record.provider_name === 'string' &&
    typeof record.provider_display_name === 'string' &&
    typeof record.url === 'string' &&
    typeof record.source_url === 'string' &&
    typeof record.display_order === 'number'
  )
}

function isSocialEmbedResolutionStatus(value: unknown): value is SocialEmbedResolutionStatus {
  return ['pending', 'resolved', 'error'].includes(String(value))
}

function isSocialEmbedRecord(value: unknown): value is SocialEmbedRecord {
  if (!isSocialLinkRecord(value)) {
    return false
  }

  return (
    'resolution_status' in value &&
    isSocialEmbedResolutionStatus(value.resolution_status) &&
    'resolution_error' in value &&
    isOptionalString(value.resolution_error) &&
    'embed_url' in value &&
    isOptionalString(value.embed_url) &&
    'thumbnail_url' in value &&
    isOptionalString(value.thumbnail_url) &&
    'embed_width' in value &&
    isOptionalNumber(value.embed_width) &&
    'embed_height' in value &&
    isOptionalNumber(value.embed_height) &&
    'thumbnail_width' in value &&
    isOptionalNumber(value.thumbnail_width) &&
    'thumbnail_height' in value &&
    isOptionalNumber(value.thumbnail_height) &&
    'last_resolution_attempt_at' in value &&
    isOptionalString(value.last_resolution_attempt_at) &&
    'last_resolved_at' in value &&
    isOptionalString(value.last_resolved_at)
  )
}

function hasBasePayload(value: unknown, surface: PublicSocialSurface): value is SocialBasePayload {
  if (value == null || typeof value !== 'object') {
    return false
  }

  const payload = value as Record<string, unknown>
  return (
    payload.module === 'social' &&
    payload.surface === surface &&
    ['enabled', 'empty', 'disabled', 'error'].includes(String(payload.status)) &&
    typeof payload.enabled === 'boolean' &&
    typeof payload.public_path === 'string' &&
    typeof payload.integration_base_path === 'string' &&
    typeof payload.integration_embeds_path === 'string' &&
    isStringArray(payload.provider_allowlist) &&
    isStringArray(payload.embed_provider_allowlist) &&
    (payload.error === null || typeof payload.error === 'string')
  )
}

function isLinkTreePayload(value: unknown): value is SocialLinkTreePayload {
  if (!hasBasePayload(value, 'link_tree')) {
    return false
  }

  return (
    'layout_variant' in value &&
    typeof value.layout_variant === 'string' &&
    'links_per_page' in value &&
    typeof value.links_per_page === 'number' &&
    'total_links' in value &&
    typeof value.total_links === 'number' &&
    'links' in value &&
    Array.isArray(value.links) &&
    value.links.every(isSocialLinkRecord)
  )
}

function isEmbedsPayload(value: unknown): value is SocialEmbedsPayload {
  if (!hasBasePayload(value, 'embeds')) {
    return false
  }

  return (
    'cache_ttl_seconds' in value &&
    typeof value.cache_ttl_seconds === 'number' &&
    'embeds_per_page' in value &&
    typeof value.embeds_per_page === 'number' &&
    'total_embeds' in value &&
    typeof value.total_embeds === 'number' &&
    'embeds' in value &&
    Array.isArray(value.embeds) &&
    value.embeds.every(isSocialEmbedRecord)
  )
}

async function fetchPublicSocialPayload<TSurface extends PublicSocialSurface>(
  surface: TSurface,
  endpoint: string,
): Promise<SocialPayloadBySurface[TSurface]> {
  let payload: unknown
  let transportError: ApiError | null = null

  try {
    payload = await apiRequest<unknown>(endpoint)
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error
    }
    // The managed payload states its own error and disabled conditions, and
    // the endpoint answers those with an error status; validate the body
    // before letting the transport failure stand.
    transportError = error
    payload = error.data
  }

  if (surface === 'link_tree' && isLinkTreePayload(payload)) {
    return payload as SocialPayloadBySurface[TSurface]
  }

  if (surface === 'embeds' && isEmbedsPayload(payload)) {
    return payload as SocialPayloadBySurface[TSurface]
  }

  if (transportError) {
    // The one QuickScale error shape's message, or the status fallback, so
    // the page shows the transport failure instead of contract-mismatch text.
    throw transportError
  }

  // The managed payload is the domain contract; a success body that does not
  // match it is the page's own contract-mismatch failure.
  throw new ApiError(
    200,
    `QuickScale social ${surface} payload did not match the managed contract`,
    payload,
  )
}

export function usePublicSocialSurface<TSurface extends PublicSocialSurface>(surface: TSurface) {
  const config = useProjectConfig()
  const publicPage = config.publicPage?.surface === surface ? config.publicPage : undefined
  // The managed seam's publicPage config carries the module's endpoint; the
  // client never guesses a module path when the producer did not supply one.
  const endpoint = publicPage?.endpoint
  const navigation = publicPage?.navigation ?? DEFAULT_NAVIGATION

  const query = useQuery<SocialPayloadBySurface[TSurface], Error>({
    queryKey: ['public-social', surface, endpoint ?? ''],
    queryFn: () => {
      if (!endpoint) {
        throw new Error(
          'The public page config is missing the managed social endpoint.',
        )
      }
      return fetchPublicSocialPayload(surface, endpoint)
    },
    enabled: Boolean(endpoint),
    retry: false,
  })

  return {
    projectName: config.projectName,
    endpoint,
    navigation,
    ...query,
  }
}
