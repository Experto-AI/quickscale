import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Checkbox } from '@/components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

// Radix primitives call browser APIs jsdom does not implement.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.releasePointerCapture = vi.fn()
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

describe('checkbox primitive', () => {
  it('toggles its checked state through user interaction', async () => {
    const user = userEvent.setup()
    render(<Checkbox aria-label="Accept terms" />)

    const checkbox = screen.getByRole('checkbox', { name: 'Accept terms' })
    expect(checkbox).toHaveAttribute('data-state', 'unchecked')

    await user.click(checkbox)
    expect(checkbox).toHaveAttribute('data-state', 'checked')

    await user.click(checkbox)
    expect(checkbox).toHaveAttribute('data-state', 'unchecked')
  })
})

describe('radio group primitive', () => {
  it('selects one option at a time', async () => {
    const user = userEvent.setup()
    render(
      <RadioGroup aria-label="Plan">
        <RadioGroupItem value="basic" aria-label="Basic" />
        <RadioGroupItem value="pro" aria-label="Pro" />
      </RadioGroup>,
    )

    const basic = screen.getByRole('radio', { name: 'Basic' })
    const pro = screen.getByRole('radio', { name: 'Pro' })

    await user.click(pro)
    expect(pro).toHaveAttribute('data-state', 'checked')
    expect(basic).toHaveAttribute('data-state', 'unchecked')

    await user.click(basic)
    expect(basic).toHaveAttribute('data-state', 'checked')
    expect(pro).toHaveAttribute('data-state', 'unchecked')
  })
})

describe('textarea primitive', () => {
  it('accepts typed text', async () => {
    const user = userEvent.setup()
    render(<Textarea placeholder="Notes" />)

    const textarea = screen.getByPlaceholderText('Notes')
    await user.type(textarea, 'Hello')
    expect(textarea).toHaveValue('Hello')
  })
})

describe('separator primitive', () => {
  it('renders horizontal and vertical orientations', () => {
    const { container } = render(
      <div>
        <Separator data-testid="horizontal" />
        <Separator data-testid="vertical" orientation="vertical" />
      </div>,
    )

    expect(screen.getByTestId('horizontal')).toHaveAttribute('data-orientation', 'horizontal')
    expect(screen.getByTestId('vertical')).toHaveAttribute('data-orientation', 'vertical')
    expect(container.querySelector('.h-\\[1px\\]')).not.toBeNull()
    expect(container.querySelector('.w-\\[1px\\]')).not.toBeNull()
  })
})

describe('select primitive', () => {
  it('opens, selects an option, and renders groups, labels, and separators', async () => {
    const user = userEvent.setup()
    render(
      <Select defaultValue="one">
        <SelectTrigger aria-label="Pick a number">
          <SelectValue placeholder="Pick one" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Numbers</SelectLabel>
            <SelectItem value="one">One</SelectItem>
            <SelectItem value="two">Two</SelectItem>
            <SelectSeparator />
            <SelectItem value="three">Three</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>,
    )

    const trigger = screen.getByRole('combobox', { name: 'Pick a number' })
    expect(trigger).toHaveTextContent('One')

    await user.click(trigger)
    expect(await screen.findByText('Numbers')).toBeInTheDocument()
    await user.click(await screen.findByRole('option', { name: 'Two' }))

    expect(trigger).toHaveTextContent('Two')
  })

  it('renders item-aligned content without the popper offsets', async () => {
    const user = userEvent.setup()
    render(
      <Select>
        <SelectTrigger aria-label="Aligned picker">
          <SelectValue placeholder="Choose" />
        </SelectTrigger>
        <SelectContent position="item-aligned">
          <SelectItem value="alpha">Alpha</SelectItem>
        </SelectContent>
      </Select>,
    )

    await user.click(screen.getByRole('combobox', { name: 'Aligned picker' }))
    await user.click(await screen.findByRole('option', { name: 'Alpha' }))

    expect(screen.getByRole('combobox', { name: 'Aligned picker' })).toHaveTextContent('Alpha')
  })
})

describe('tooltip primitive', () => {
  it('renders content when open', async () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip defaultOpen>
          <TooltipTrigger>Hover target</TooltipTrigger>
          <TooltipContent sideOffset={8}>Tip body</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    )

    expect(await screen.findByRole('tooltip')).toHaveTextContent('Tip body')
  })
})
