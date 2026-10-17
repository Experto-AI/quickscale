# Start Here

QuickScale generates standalone Django SaaS projects that you own completely. Optional
first-party modules (analytics, auth, backups, billing, blog, crm, forms, listings,
notifications, orgs, social, storage) are embedded with git subtree. The `showcase_react`
starter theme is generated once into project code.

```bash
quickscale plan myapp   # interactive config → quickscale.yml
cd myapp
quickscale apply        # generate / sync the project
quickscale up           # run it in Docker
```

## Read by goal

| Goal | Read |
|---|---|
| Evaluate QuickScale | [README.md](README.md) → [overview/quickscale.md](docs/overview/quickscale.md) → [competitive_analysis.md](docs/overview/competitive_analysis.md) |
| Build a project | [README.md](README.md) Quick Start → [user_manual.md](docs/technical/user_manual.md) |
| Deploy | [deployment/railway.md](docs/deployment/railway.md) |
| Contribute | [contrib/contributing.md](docs/contrib/contributing.md) → [development.md](docs/technical/development.md) |
| Understand architecture | [decisions.md](docs/technical/decisions.md) → [plan-apply-system.md](docs/technical/plan-apply-system.md) → [generated_project_structure.md](docs/technical/generated_project_structure.md) |
| Write or extend a module | [module-extension.md](docs/technical/module-extension.md) → any `quickscale_modules/<name>/README.md` |
| Look up a term | [GLOSSARY.md](GLOSSARY.md) |
| See what is planned or shipped | [roadmap.md](docs/technical/roadmap.md) / [CHANGELOG.md](CHANGELOG.md) |

Every document is listed in [docs/index.md](docs/index.md). [decisions.md](docs/technical/decisions.md)
wins any conflict; its [§ Document Responsibilities](docs/technical/decisions.md#document-responsibilities)
names the owner of every topic.
