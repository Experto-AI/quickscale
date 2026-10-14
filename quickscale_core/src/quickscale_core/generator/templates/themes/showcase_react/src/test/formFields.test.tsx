import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FormRenderer } from '@/components/forms/FormRenderer'
import type { FormFieldSchema, FormSchema } from '@/hooks/useFormSchema'
import { moduleFlags, modulePaths, moduleApiPaths } from '@/test/seamFixtures'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  window.__QUICKSCALE__ = {
    projectName: 'formFields Test',
    modules: moduleFlags({ forms: true }),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    owner: { mode: 'solo', currentOrgSlug: null },
  }
})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.releasePointerCapture = vi.fn()
  // Direct definition so a per-test location stub can never clear it.
  Object.defineProperty(globalThis, 'ResizeObserver', {
    value: ResizeObserverStub,
    writable: true,
    configurable: true,
  })
})

afterAll(() => {
  Reflect.deleteProperty(globalThis, 'ResizeObserver')
})

function jsonResponse(status: number, payload: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
  } as Response
}

function field(
  name: string,
  fieldType: FormFieldSchema['field_type'],
  order: number,
  overrides: Partial<FormFieldSchema> = {},
): FormFieldSchema {
  return {
    name,
    field_type: fieldType,
    label: name,
    required: false,
    order,
    layout_hint: 'half_left',
    options: [],
    validation_rules: {},
    is_active: true,
    ...overrides,
  }
}

function buildSchema(overrides: Partial<FormSchema> = {}): FormSchema {
  return {
    slug: 'contact',
    title: 'Contact',
    description: 'Tell us about your project.',
    success_message: 'Thanks for your message.',
    fields: [
      field('full_name', 'text', 0, {
        label: 'Full name',
        required: true,
        layout_hint: 'full',
        help_text: 'As written on your ID.',
      }),
      field('bio', 'textarea', 1, { placeholder: 'Short bio' }),
      field('topic', 'select', 2, {
        options: [
          { value: 'a', label: 'Topic A' },
          { value: 'b', label: 'Topic B' },
        ],
        placeholder: 'Enter topic',
      }),
      field('source', 'select', 3, {
        label: 'Source',
        options: [{ value: 'search', label: 'Search' }],
      }),
      field('subscribe', 'checkbox', 4, { placeholder: 'Subscribe to updates' }),
      field('plan', 'radio', 5, {
        options: [
          { value: 'basic', label: 'Basic' },
          { value: 'pro', label: 'Pro' },
        ],
      }),
      field('email', 'email', 6, { label: 'Email', required: true }),
      field('website', 'url', 7, { label: 'Website' }),
      field('age', 'number', 8, { label: 'Age' }),
      field('code', 'text', 9, {
        label: 'Code',
        required: true,
        validation_rules: { min_length: 2, max_length: 5, regex: '^[a-z]+$' },
      }),
      field('secret', 'hidden', 10, { label: 'Secret', required: true }),
      field('_hp_name', 'text', 11, { label: 'Leave empty' }),
      field('retired', 'text', 12, { is_active: false }),
    ],
    ...overrides,
  }
}

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <FormRenderer slug="contact" />
    </QueryClientProvider>,
  )
}

async function loadForm(schema: FormSchema = buildSchema()) {
  fetchMock.mockResolvedValueOnce(jsonResponse(200, schema))
  renderForm()
  return screen.findByLabelText(/email/i)
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: /^submit$/i }))
}

function fill(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

afterEach(() => {
  fetchMock.mockReset()
})

describe('form field rendering', () => {
  it('renders each field type from the schema', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, buildSchema()))
    const { container } = renderForm()
    await screen.findByLabelText(/email/i)

    expect(screen.getByText('Tell us about your project.')).toBeInTheDocument()
    expect(screen.getByText('As written on your ID.')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Short bio')).toBeInTheDocument()
    expect(screen.getByText('Subscribe to updates')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Basic' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Pro' })).toBeInTheDocument()
    expect(screen.getByText('Enter topic')).toBeInTheDocument()
    expect(screen.getByText('Select Source')).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
    expect(container.querySelector('input[type="hidden"][name="secret"]')).not.toBeNull()
    expect(container.querySelector('input[name="retired"]')).toBeNull()
  })

  it('validates required and typed fields locally before submitting', async () => {
    await loadForm()

    submit()
    expect(await screen.findByText('Full name is required')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fill(/full name/i, 'Alice')
    fill(/email/i, 'not-an-email')
    fill(/website/i, 'not-a-url')
    fill(/age/i, 'abc')
    fill(/code/i, 'A')
    submit()

    expect(await screen.findByText('Please enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('Please enter a valid URL')).toBeInTheDocument()
    expect(screen.getByText('Minimum 2 characters')).toBeInTheDocument()

    fill(/code/i, 'abcdef')
    submit()
    expect(await screen.findByText('Maximum 5 characters')).toBeInTheDocument()

    fill(/code/i, '12')
    submit()
    expect(await screen.findByText('Invalid format')).toBeInTheDocument()
  })

  it('drives select, checkbox, and radio controls from user input', async () => {
    await loadForm()
    const user = userEvent.setup()

    const [topicTrigger] = screen.getAllByRole('combobox')
    await user.click(topicTrigger)
    await user.click(await screen.findByRole('option', { name: 'Topic B' }))
    expect(topicTrigger).toHaveTextContent('Topic B')

    const checkbox = screen.getByRole('checkbox')
    await user.click(checkbox)
    expect(checkbox).toHaveAttribute('data-state', 'checked')

    await user.click(screen.getByRole('radio', { name: 'Pro' }))
    expect(screen.getByRole('radio', { name: 'Pro' })).toHaveAttribute('data-state', 'checked')
  })

  it('submits successfully, shows the success card, and resets on request', async () => {
    await loadForm()
    fetchMock.mockResolvedValueOnce(jsonResponse(200, {}))

    fill(/full name/i, 'Alice')
    fill(/email/i, 'alice@example.com')
    fill(/website/i, 'https://example.com')
    fill(/code/i, 'abc')
    submit()

    expect(await screen.findByText('Thanks for your message.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/forms/api/contact/submit/',
      expect.objectContaining({ method: 'POST' }),
    )

    fireEvent.click(screen.getByRole('button', { name: /submit another response/i }))

    expect(await screen.findByRole('button', { name: /^submit$/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/full name/i)).toHaveValue('')
  })

  it('navigates to the schema redirect URL after a successful submit', async () => {
    const assign = vi.fn()
    const originalLocation = window.location
    // Restore only the location override; vi.unstubAllGlobals() would also
    // drop the file-level fetch stub and break later tests.
    vi.stubGlobal('location', { assign })
    try {
      await loadForm(buildSchema({ redirect_url: '/thanks/' }))
      fetchMock.mockResolvedValueOnce(jsonResponse(200, {}))

      fill(/full name/i, 'Alice')
      fill(/email/i, 'alice@example.com')
      fill(/website/i, 'https://example.com')
      fill(/code/i, 'abc')
      submit()

      await waitFor(() => expect(assign).toHaveBeenCalledWith('/thanks/'))
      expect(screen.queryByText('Thanks for your message.')).toBeNull()
    } finally {
      vi.stubGlobal('location', originalLocation)
    }
  })
})
