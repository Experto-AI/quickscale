# quickscale-cli

Command-line interface package for QuickScale.

This package exposes the `quickscale` command used to plan, apply, inspect, recover, and operate generated projects.

## Command groups

- Project lifecycle: `plan`, `apply`, `status`, `remove`
- Disaster recovery & promotion: `dr capture`, `dr plan`, `dr execute`, `dr report`
- Local development: `up`, `down`, `ps`, `logs`, `shell`, `manage`
- Deployment: `deploy`
- Module workflows: `update`, `push`

## Relationship to other packages

- `quickscale-cli` is the command surface
- `quickscale-core` contains the underlying scaffolding and template logic
- `quickscale` installs both together for convenience

## Install

Usually installed via the meta-package:

```bash
pip install quickscale
```

Standalone package installs can use this package's published metadata and dependency constraints.

## Documentation

- Repository overview: [QuickScale README](https://github.com/Experto-AI/quickscale/blob/main/README.md)
- Start guide: [START_HERE.md](https://github.com/Experto-AI/quickscale/blob/main/START_HERE.md)
- Technical decisions: [docs/technical/decisions.md](https://github.com/Experto-AI/quickscale/blob/main/docs/technical/decisions.md)
- CLI source entrypoint: [src/quickscale_cli/main.py](https://github.com/Experto-AI/quickscale/blob/main/quickscale_cli/src/quickscale_cli/main.py)

This README is package-local context only. Root documentation remains authoritative for repo-wide policy and scope.
