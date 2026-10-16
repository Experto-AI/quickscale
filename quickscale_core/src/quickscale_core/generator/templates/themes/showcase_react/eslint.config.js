import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
  {
    // shadcn/ui components export both components and variant helpers
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // One request layer (rule 31): hook requests go through `apiRequest`,
    // which owns CSRF, the JSON contract, and the one QuickScale error shape.
    files: ['src/hooks/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.name='fetch']",
          message: 'Use apiRequest from @/hooks/useApi instead of a raw fetch().',
        },
        {
          selector: "CallExpression[callee.property.name='fetch']",
          message: 'Use apiRequest from @/hooks/useApi instead of a raw fetch().',
        },
      ],
    },
  },
  {
    // The one sanctioned request layer: the only hook that may call the
    // global fetch directly.
    files: ['src/hooks/useApi.ts'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
  {
    // Bootstrap seam: exports a render factory (not a component) alongside
    // module-level lazy() components, which fast refresh cannot track.
    // This file is only ever called once at mount, so refresh is moot.
    files: ['src/renderQuickScaleRoot.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
)
