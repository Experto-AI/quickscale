# 🚀 QuickScale

[![PyPI version](https://img.shields.io/pypi/v/quickscale.svg)](https://pypi.org/project/quickscale/)
[![CI](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml/badge.svg)](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-green.svg)](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/Experto-AI/quickscale?color=green)](https://github.com/Experto-AI/quickscale/releases)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> **Related docs**: [Start Here](START_HERE.md) | [Glossary](GLOSSARY.md) | [Decisions](docs/technical/decisions.md) | [User Manual](docs/technical/user_manual.md) | [All docs](docs/index.md)

<!-- README: first contact for users and evaluators. Max ~200 lines; link to the owning doc instead of restating it. -->

## QuickScale: Compose your Django SaaS

QuickScale is a **Django project generator and first-party module workspace** for solo developers
and agencies building repeated client SaaS projects:

- **Production foundations**: Docker, PostgreSQL, testing, CI/CD and security defaults
- **Full ownership**: generated projects are plain Django code you own, with no vendor lock-in
- **First-party modules**: analytics, auth, backups, billing, blog, crm, forms, listings,
  notifications, orgs, social, storage
- **One-command deployment**: `quickscale deploy railway`

Positioning and comparison with alternatives: [positioning.md](docs/overview/positioning.md).
The shipped surface is defined by the
[implementation surface matrix](./docs/technical/implementation_contract.md#mvp-feature-matrix-authoritative).

## Installation

```bash
pip install quickscale            # or: poetry add quickscale
```

From source: `git clone https://github.com/Experto-AI/quickscale.git && cd quickscale && ./scripts/install_global.sh`
(installs into `~/.local/share/quickscale` and links `~/.local/bin/quickscale`).
Contributors: [development.md](./docs/technical/development.md).

## Quickstart

```bash
quickscale plan myapp            # interactive wizard → myapp/quickscale.yml
cd myapp
quickscale apply                 # generate the project; Docker services auto-start by default
quickscale manage createsuperuser
quickscale ps                    # then open http://localhost:8000
```

Without Docker: `quickscale apply --no-docker`, then `poetry install`,
`poetry run python manage.py migrate` and `poetry run python manage.py runserver`.
When services auto-start and how to control them: [docker_workflows.md](./docs/technical/docker_workflows.md).

`quickscale.yml` carries two identity fields: `project.slug` (directory and service name) and
`project.package` (Python import name).

## What you get

A Django project with a React + TypeScript + shadcn/ui frontend (`showcase_react`, the only theme),
Docker for development and production, PostgreSQL, environment-split settings, pytest, GitHub
Actions CI, Ruff hooks, Poetry, and Railway deployment automation. Full layout:
[generated_project_structure.md](./docs/technical/generated_project_structure.md#generated-project-output).

## Documentation

| Need | Read |
|---|---|
| CLI commands and workflows | [user_manual.md](./docs/technical/user_manual.md) |
| Deploy to Railway | [railway.md](./docs/deployment/railway.md) |
| Rules and document ownership | [decisions.md](./docs/technical/decisions.md#document-responsibilities) |
| Frontend seam and URLs | [frontend.md](./docs/technical/frontend.md) |
| Open work / release history | [roadmap.md](./docs/technical/roadmap.md) / [CHANGELOG.md](./CHANGELOG.md) and `docs/releases/` |
| Contributing | [contrib/contributing.md](./docs/contrib/contributing.md) |
| Code quality gate (`make quality`) | [quality_tools.md](./docs/technical/quality_tools.md) |

Package READMEs ([quickscale](./quickscale/README.md), [quickscale_cli](./quickscale_cli/README.md),
[quickscale_core](./quickscale_core/README.md)) are informational; this README and decisions.md win
on any difference.

## Packages

| Directory | Role |
|---|---|
| `quickscale` | meta-package that installs the CLI and core |
| `quickscale_cli` | the `quickscale` command |
| `quickscale_core` | generator, templates, shared runtime (`dr_engine`, settings facade) |
| `quickscale_devtools` | maintainer tooling; never shipped into generated projects |
| `quickscale_modules/<name>` | one first-party module; Python package `quickscale_modules_<name>`, Django app label `quickscale_<name>` |

## License

Apache 2.0. Commercial client work and paid services on generated projects are allowed; see
[positioning.md § Commercial use](docs/overview/positioning.md#commercial-use).
