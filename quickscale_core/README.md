# quickscale-core

Core scaffolding engine and shared utilities for the QuickScale Django
project generator.

`quickscale-core` owns manifest loading, the module derivation/resolver
pipeline, the template-driven code generator, and the schema definitions
that the CLI and module packages build on.

Install it directly only when you need the library without the CLI; most
users should install the top-level `quickscale` package instead.
