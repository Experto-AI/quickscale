# {{ project_name }} - React Frontend

This is the React frontend for {{ project_name }}, built with QuickScale.

## Tech Stack

- **React 18** - UI library
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

- Node.js 18+
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
│   │   └── ui/          # shadcn/ui components
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # Utility functions
│   ├── pages/           # Page components
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

## Adding shadcn/ui Components

```bash
npx shadcn@latest add <component-name>
```

See https://ui.shadcn.com/docs/components for available components.
