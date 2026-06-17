# quickscale-cli

Command-line interface for the QuickScale Django project generator.

`quickscale-cli` provides the `quickscale` command group: lifecycle
commands (`plan`, `apply`, `status`, `remove`), disaster-recovery
workflows, local development helpers, deployment, and module update/push
operations.

All business logic lives in `quickscale-core`; this package is the
command surface only.
