// DORMANT: Forms module hook. Inert unless modules.forms is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant.
import { useQuery } from '@tanstack/react-query'

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

function normalizeApiBasePath(apiBasePath?: string): string {
  const basePath = apiBasePath ?? '/api/forms/'
  return basePath.endsWith('/') ? basePath : `${basePath}/`
}

async function fetchFormSchema(slug: string, apiBasePath?: string): Promise<FormSchema> {
  const response = await fetch(`${normalizeApiBasePath(apiBasePath)}${slug}/`)
  if (!response.ok) {
    throw new Error(`Failed to fetch form schema: ${response.statusText}`)
  }
  return response.json() as Promise<FormSchema>
}

export function useFormSchema(slug: string, apiBasePath?: string) {
  return useQuery<FormSchema, Error>({
    queryKey: ['form-schema', apiBasePath ?? '/api/forms/', slug],
    queryFn: () => fetchFormSchema(slug, apiBasePath),
    staleTime: 1000 * 60 * 10, // 10 minutes — schemas change rarely
    enabled: !!slug,
    retry: false,
  })
}
