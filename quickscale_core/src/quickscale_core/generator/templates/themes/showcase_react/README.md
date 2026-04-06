# {{ project_name }} - React Frontend

This is the React frontend for {{ project_name }}, built with QuickScale.

## Shipped Surface

This directory comes from QuickScale's current `showcase_react` starter theme. In the
current release line, QuickScale ships two starter themes only:

- `showcase_react` - React + TypeScript + shadcn/ui (this frontend)
- `showcase_html` - server-rendered HTML + CSS

Fresh `showcase_react` generations also include dormant PostHog starter support in
`src/lib/analytics.ts` and Django-owned public social entrypoints at `/social` and
`/social/embeds` that hydrate the shared React bundle outside the SPA router.

## Tech Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS
- **shadcn/ui** - Component library
- **React Router** - Client-side routing
- **TanStack Query** - Server state management
- **Zustand** - Client state management
- **React Hook Form + Zod** - Form handling and validation
- **Vitest + RTL** - Testing

## Getting Started

### Prerequisites

- Node.js 24+
- pnpm (required)

### Installation

```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev
```

The frontend will be available at http://localhost:5173

### Development

The development server proxies API requests to the Django backend at http://localhost:8000.

The dormant analytics helper only initializes when `VITE_POSTHOG_KEY` contains a real
PostHog project key. Leave it unset for the default no-op starter behavior.

```bash
# Run tests
pnpm test

# Run tests with coverage
pnpm test:coverage

# Lint code (ESLint)
pnpm lint

# Lint and auto-fix
pnpm lint:fix

# TypeScript type check
pnpm type-check

# Run all lint checks (type-check + ESLint)
pnpm lint:all

# Format with Prettier
pnpm format

# Check formatting (CI-friendly)
pnpm format:check

# Build for production
pnpm build
```

### Production Build

```bash
pnpm build
```

This outputs the built files to `../static/frontend/` for Django to serve.

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/
│   │   ├── layout/      # Layout components (Header, Sidebar, etc.)
│   │   ├── social/      # Django-owned public social shell
│   │   └── ui/          # shadcn/ui components
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # Shared utilities + dormant analytics helper
│   ├── pages/           # SPA pages + Django-owned public social pages
│   ├── stores/          # Zustand stores
│   ├── test/            # Test utilities and setup
│   ├── App.tsx          # Main app component
│   └── main.tsx         # Entry point
├── index.html           # HTML template
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

The generated Django project also includes `templates/social/link_tree.html` and
`templates/social/embeds.html`, which keep those public routes under Django ownership while
bootstrapping `window.__QUICKSCALE__.publicPage` for the shared React bundle.

## Adding shadcn/ui Components

```bash
npx shadcn@latest add <component-name>
```

See https://ui.shadcn.com/docs/components for available components.
