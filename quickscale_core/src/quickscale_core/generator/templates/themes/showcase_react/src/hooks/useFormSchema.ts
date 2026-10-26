// DORMANT: Forms module hook. Inert unless modules.forms is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant.
import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '@/hooks/useApi'
import { useProjectConfig } from '@/hooks/useModules'
import { FORMS_RESOURCE_PATHS } from '@/quickscaleSeam.hooks'

import type {
  FieldType,
  FormFieldOption,
  FormFieldSchema,
  FormSchema,
  LayoutHint,
  ValidationRules,
} from '@/quickscaleSeam.hooks'

// The schema types live in the managed hook file; the hook re-exports them for
// the form components and tests that import this module.
export type {
  FieldType,
  FormFieldOption,
  FormFieldSchema,
  FormSchema,
  LayoutHint,
  ValidationRules,
}

function normalizeApiBasePath(apiBasePath: string): string {
  return apiBasePath.endsWith('/') ? apiBasePath : `${apiBasePath}/`
}

async function fetchFormSchema(slug: string, apiBasePath: string): Promise<FormSchema> {
  // The shared client owns transport, CSRF, and the one QuickScale error
  // shape (rule 31); a failed schema fetch carries the shape's message.
  return apiRequest<FormSchema>(
    `${normalizeApiBasePath(apiBasePath)}${FORMS_RESOURCE_PATHS.schema(slug)}`,
  )
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
