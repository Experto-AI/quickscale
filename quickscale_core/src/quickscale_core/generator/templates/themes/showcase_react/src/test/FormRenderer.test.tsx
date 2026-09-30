import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FormRenderer } from '@/components/forms/FormRenderer'
import type { FormSchema } from '@/hooks/useFormSchema'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function buildFormSchema(): FormSchema {
  return {
    slug: 'contact',
    title: 'Contact',
    success_message: 'Thanks for your message.',
    fields: [
      {
        name: 'full_name',
        field_type: 'text',
        label: 'Full name',
        required: true,
        order: 0,
        layout_hint: 'full',
        options: [],
        validation_rules: {},
        is_active: true,
      },
    ],
  }
}

function jsonResponse(status: number, payload: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
  } as Response
}

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <FormRenderer slug="contact" />
    </QueryClientProvider>,
  )
}

async function loadForm(schema: FormSchema = buildFormSchema()) {
  fetchMock.mockResolvedValueOnce(jsonResponse(200, schema))
  renderForm()
  return screen.findByLabelText(/full name/i)
}

function fillFullName(value: string) {
  fireEvent.change(screen.getByLabelText(/full name/i), { target: { value } })
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: /submit/i }))
}

afterEach(() => {
  fetchMock.mockReset()
})

describe('form client error handling', () => {
  it('shows a validation error from the one QuickScale shape on its field', async () => {
    await loadForm()
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: { full_name: ['This name is already registered.'] },
        },
      }),
    )

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('This name is already registered.'),
    ).toBeInTheDocument()
  })

  it('shows a non-field validation error as a global error', async () => {
    await loadForm()
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: { non_field_errors: ['This form was already submitted.'] },
        },
      }),
    )

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('This form was already submitted.'),
    ).toBeInTheDocument()
  })

  it('shows a server field the rendered schema does not know as a global error', async () => {
    await loadForm()
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: { new_field: ['This field is required.'] },
        },
      }),
    )

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('new_field: This field is required.'),
    ).toBeInTheDocument()
  })

  it('shows a server error for a hidden field as a global error', async () => {
    const schema = buildFormSchema()
    schema.fields.push({
      name: 'tracking_token',
      field_type: 'hidden',
      label: 'Tracking token',
      required: false,
      order: 1,
      layout_hint: 'full',
      options: [],
      validation_rules: {},
      is_active: true,
    })
    await loadForm(schema)
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: { tracking_token: ['Invalid tracking token.'] },
        },
      }),
    )

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('tracking_token: Invalid tracking token.'),
    ).toBeInTheDocument()
  })

  it('does not block submission locally on a required hidden field', async () => {
    const schema = buildFormSchema()
    schema.fields.push({
      name: 'tracking_token',
      field_type: 'hidden',
      label: 'Tracking token',
      required: true,
      order: 1,
      layout_hint: 'full',
      options: [],
      validation_rules: {},
      is_active: true,
    })
    await loadForm(schema)
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: { tracking_token: ['This field is required.'] },
        },
      }),
    )

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('tracking_token: This field is required.'),
    ).toBeInTheDocument()
  })

  it("shows the one shape's message for a non-validation error", async () => {
    await loadForm()
    fetchMock.mockResolvedValueOnce(
      jsonResponse(429, {
        error: {
          code: 'throttled',
          message: 'Request was throttled. Expected available in 59 seconds.',
        },
      }),
    )

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('Request was throttled. Expected available in 59 seconds.'),
    ).toBeInTheDocument()
  })

  it('keeps the network message when the request cannot be made', async () => {
    await loadForm()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    fillFullName('Alice')
    submit()

    expect(
      await screen.findByText('Network error. Please check your connection and try again.'),
    ).toBeInTheDocument()
  })

  it("shows the one shape's message when the form schema cannot be fetched", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(404, {
        error: { code: 'not_found', message: 'Not found.' },
      }),
    )
    renderForm()

    expect(await screen.findByText('Not found.')).toBeInTheDocument()
  })
})
