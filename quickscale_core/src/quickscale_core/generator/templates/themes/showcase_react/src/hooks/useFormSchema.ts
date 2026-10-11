// DORMANT: Forms module hook. Inert unless modules.forms is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant.
import { useQuery } from '@tanstack/react-query'
import { ApiError, getApiPayloadMessage } from '@/hooks/useApi'
import { useProjectConfig } from '@/hooks/useModules'

export interface FormFieldOption {
  value: string
  label: string
}

export interface ValidationRules {
  min_length?: number
  max_length?: number
  min?: number
  max?: number
  regex?: string
}

export type FieldType =
  | 'text'
  | 'email'
  | 'textarea'
  | 'select'
  | 'checkbox'
  | 'radio'
  | 'number'
  | 'url'
  | 'tel'
  | 'date'
  | 'hidden'

export type LayoutHint = 'full' | 'half_left' | 'half_right'

export interface FormFieldSchema {
  name: string
  field_type: FieldType
  label: string
  required: boolean
  order: number
  placeholder?: string
  help_text?: string
  layout_hint: LayoutHint
  options: FormFieldOption[]
  validation_rules: ValidationRules
  is_active: boolean
}

export interface FormSchema {
  slug: string
  title: string
  description?: string
  success_message: string
  redirect_url?: string
  fields: FormFieldSchema[]
}

function normalizeApiBasePath(apiBasePath: string): string {
  return apiBasePath.endsWith('/') ? apiBasePath : `${apiBasePath}/`
}

async function fetchFormSchema(slug: string, apiBasePath: string): Promise<FormSchema> {
  const response = await fetch(`${normalizeApiBasePath(apiBasePath)}${slug}/`)
  if (!response.ok) {
    // Surface the one QuickScale error shape's message when the endpoint
    // answers it, and keep the generic text otherwise.
    const payload = await response.json().catch(() => null)
    throw new ApiError(
      response.status,
      getApiPayloadMessage(payload) ?? `Failed to fetch form schema: ${response.statusText}`,
      payload,
    )
  }
  return response.json() as Promise<FormSchema>
}

export function useFormSchema(slug: string, apiBasePath?: string) {
  const { moduleApiPaths } = useProjectConfig()
  const formsApiBasePath = normalizeApiBasePath(apiBasePath ?? moduleApiPaths.forms)

  return useQuery<FormSchema, Error>({
    queryKey: ['form-schema', formsApiBasePath, slug],
    queryFn: () => fetchFormSchema(slug, formsApiBasePath),
    staleTime: 1000 * 60 * 10, // 10 minutes — schemas change rarely
    enabled: !!slug,
    retry: false,
  })
}
