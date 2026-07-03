# Tech Audit: Fail-Hard Violations

> **Audit date:** 2026-07-03 · **Branch:** `v87`
> **Policy audited against:** [decisions.md §fail-hard-principle](docs/technical/decisions.md#fail-hard-principle) — no silent fallbacks, no best-effort defaults, no graceful degradation, no backward-compat shims; every misconfiguration must raise an explicit, descriptive error.
>
> This file records **found-not-yet-fixed** violations for later remediation planning. Structural findings live in [arch-audit.md](arch-audit.md); once a finding here is remediated, drop it and log the closeout in [CHANGELOG.md](CHANGELOG.md).

**Scope swept:** `quickscale_core/src`, `quickscale_cli/src`, `quickscale_modules/*/src`, `scripts/`, generator templates. Patterns: broad/silent `except`, fallback chains, legacy/compat keywords, `getattr(settings, X, default)`, env-var defaults.

**Exemptions honored (not findings):** DR engine fallback artifacts and `QUICKSCALE_ENVIRONMENT` defaulting (explicitly out of scope per §fail-hard-principle); `project_state.py:_read_through_import_legacy()` (documented exception F12.2); domain logic inside generated projects. Positive examples confirmed: `entry_point.py:239` raises `ImproperlyConfigured` on adapter import failure; `billing/services.py:434` raises `BillingConfigurationError` on missing Stripe SDK.

---

## Findings summary

| ID | Severity | Location | One-liner |
|----|----------|----------|-----------|
| TA1 | High | `quickscale_core/contracts/resolvers.py` | Legacy config keys silently translated/dropped instead of rejected |
| TA2 | High | `quickscale_modules/*/src` (pervasive) | `getattr(settings, X, permissive-default)` — features fail-open when settings are missing (generalizes SA11.7) |
| TA3 | High | `quickscale_core/manifest/entry_point.py:1399` | Import-time `except Exception: pass` around adapter registry init |
| TA4 | Medium | `quickscale_core/manifest/entry_point.py:302` | Analytics "fallback defaults matching legacy behaviour" silently fill empty settings |
| TA5 | Medium | `quickscale_cli/src/quickscale_cli/schema/` | Undocumented backward-compat shim package; CLI's own code still imports through it |
| TA6 | Medium | `quickscale_core/generator/generator.py` | Template-dir discovery fallback chain + root-template compat fallback |
| TA7 | Medium | `quickscale_core/version.py:16` | Version fallback chain ending in silent `"0.0.0"` default |
| TA8 | Medium | `quickscale_core/project_state.py:655` | Metadata resolution falls back state.yml → quickscale.yml → `None`, swallowing validation errors |
| TA9 | Medium | `analytics/services.py:218`, `forms/views.py:92` | Missing SDK / missing sibling module degrades silently instead of failing |
| TA10 | Medium | `quickscale_cli/utils/railway_utils.py` | Broad `except Exception: return None` hides Railway CLI errors |
| TA11 | Low | `quickscale_cli/utils/docker_utils.py:164` | Invalid `PORT` env value silently coerced to 8000 |
| TA12 | Low | `quickscale_core/contracts/module_catalog.py` | Deprecated compat delegates still in public API; unknown module names fail-open in readiness check |
| TA13 | Low | `quickscale_core/apply/steps/wiring.py:71` | Best-effort hash-capture step always reports success |
| TA14 | Low | repo-wide | `# F-EXCEPTION:` tag mandated by decisions.md appears nowhere in code |
| TA15 | Low | `scripts/check_module_core_compatibility.py:381` | `except Exception: return None` on pyproject parse in dev tooling |

---

## Findings detail

### TA1 (High) — Legacy config keys silently translated or dropped

`contracts/resolvers.py`: `normalize_auth_module_options()` (≈:222–233) silently maps legacy `modules.auth.allow_registration` → `registration_enabled` and silently **drops** `modules.auth.social_providers`. Same pattern for CRM `default_pipeline_stages` (`:556`) and `_LEGACY_NOTIFICATIONS_SECRET_OPTIONS` (`:780`). The "Remove legacy keys like…" guidance exists only in `format_auth_desired_config_contract()` (`:252`), a help formatter — normalization itself never raises. A user with a stale `quickscale.yml` gets no signal that their keys are dead; a dropped `social_providers` key changes behavior with zero feedback. Contradicts the "clean break, no migration path" constraint. **Fix direction:** raise `ConfigValidationError` naming the legacy key and its replacement.

### TA2 (High) — Pervasive permissive settings defaults across modules

SA11.7 (tracked in decisions.md Known violations) covers `auth/adapters.py:14` (`ACCOUNT_ALLOW_REGISTRATION` defaults `True`), but the pattern is systemic — missing Django settings silently enable features or invent values instead of raising `ImproperlyConfigured`:

- `analytics/services.py:61` — `QUICKSCALE_ANALYTICS_ENABLED` defaults `True`
- `billing/services.py:117` — `QUICKSCALE_BILLING_ENABLED` defaults `True`
- `crm/views.py:219,238,246` — `CRM_ENABLE_API` defaults `True`; page sizes `int(getattr(...) or 50)` also swallow invalid values
- `forms/views.py:134,146`, `forms/throttles.py:16`, `forms/models.py:32` — submissions API on, rate limit `"5/hour"`, spam protection flag defaulted
- `blog/urls.py:18`, `blog/views.py:175,280`, `blog/models.py:46-48` — RSS on by default; `BLOG_API_TOKENS` defaults `[]` with malformed entries silently `continue`-skipped (`views.py:181-190`); media URL invented
- `notifications/services.py:155-157` — enabled defaults `True`, provider defaults `"resend"`

Since modules are creation-time assembled and the generator owns settings emission, every one of these settings is knowable at generation time; the defaults exist only to mask incomplete wiring. **Fix direction:** module `apps.py` startup checks (Django system checks) that raise on missing required settings; generator guarantees emission.

### TA3 (High) — Import-time `except Exception: pass` in manifest adapter init

`manifest/entry_point.py:1399-1403`: module-level `try: refresh_managed_adapters() ... except Exception: pass`. The comment justifies swallowing *circular-import* errors with lazy re-init on first `build_manifest_wiring_spec()` call, but the clause swallows **all** exceptions — a genuinely broken adapter (syntax error, bad registration) is masked at import and resurfaces later, farther from the root cause. This is the literal prohibited pattern ("no `except Exception: pass` in … discovery paths"). **Fix direction:** narrow to the specific circular-import case (or eliminate the import-time eager init entirely) and add an F-EXCEPTION entry if any swallowing must remain.

### TA4 (Medium) — Analytics fallback defaults in manifest resolution

`manifest/entry_point.py:302-311`: after resolution, empty analytics settings are silently replaced with hardcoded defaults (`QUICKSCALE_ANALYTICS_PROVIDER="posthog"`, env-var names, `POSTHOG_HOST="https://us.i.posthog.com"`) — commented as "Fallback defaults matching legacy behaviour." Best-effort defaults inside the manifest stack, explicitly in scope for fail-hard. Empty-after-resolution means the manifest/derivation produced an invalid result and should raise.

### TA5 (Medium) — Undocumented backward-compat shim package `quickscale_cli.schema`

`quickscale_cli/src/quickscale_cli/schema/{__init__,config_schema,state_schema,delta}.py` are self-described "backward-compatible shims" re-exporting the relocated `quickscale_core.schema` package. Not in the decisions.md F-EXCEPTION table (which is mandatory for shims), has no sunset plan, and — worse — the CLI's **own internal code** still imports through it (`utils/project_manager.py:6`, `utils/module_wiring_manager.py:21-22`, `commands/plan_command.py:27,36`, `commands/remove_command.py`), so the "temporary" indirection has become load-bearing. With no external users (per the global no-users constraint), there is nothing to be compatible *with*. **Fix direction:** migrate internal imports to `quickscale_core.schema` and delete the shim package.

### TA6 (Medium) — Generator template fallback chains

`generator/generator.py`:
- `__init__` (`:96-131`): template-dir discovery tries dev dir → package dir → three guessed layouts including `Path.cwd()`-relative — silently picks the first hit. A `FileNotFoundError` is raised only if *all* guesses miss; a wrong-but-existing hit (e.g. cwd-dependent) is used without a word.
- `_get_theme_template_path` (`:165-178`): theme → common → root fallback, the last explicitly "for backward compatibility" and returned **without an existence check** (error surfaces later as a Jinja `TemplateNotFound` far from the cause).

**Fix direction:** single deterministic resolution rule (installed package path, explicit override param), raise immediately with the attempted path on miss; delete the root-template compat tier.

### TA7 (Medium) — Version fallback chain ending in `"0.0.0"`

`quickscale_core/version.py:16-27`: `from ._version import __version__` wrapped in `except Exception` (not `ImportError`), falling back to the repo `VERSION` file, falling back to hardcoded `"0.0.0"`. A broken build (missing `_version.py` in a wheel, missing VERSION file) silently reports version `0.0.0` instead of failing — poisoning version-gated behavior and support diagnostics. The dev-tree read is legitimate; the terminal `"0.0.0"` default and the over-broad except are not.

### TA8 (Medium) — Project-metadata resolution swallows validation errors

`project_state.py` `resolve_authoritative_project_metadata` (≈:640-679): falls back `state.yml` → `quickscale.yml` → `None`, and the `quickscale.yml` branch wraps `validate_config` in `except Exception: return None` — a malformed/invalid `quickscale.yml` is indistinguishable from "no project here." Related: `_load_managed_file_records_for_drift` (≈:600) reads legacy `file_hashes.yml` as a fallback — same M2 family as F12.2 but a different function, not covered by the documented exception's stated location. **Fix direction:** let validation errors propagate (the file exists but is broken → tell the user); extend or properly scope F12.2 for the drift-read path.

### TA9 (Medium) — Optional-dependency graceful degradation in modules

- `analytics/services.py:218-223`: PostHog SDK import failure → `logger.warning(... "Analytics capture remains disabled.")` — textbook graceful degradation. If analytics is assembled into the project, its SDK is a required dependency.
- `forms/views.py:92-97`: `import_module("quickscale_modules_analytics.services")` with `except ImportError: return`, then `getattr(..., None)` probing — a soft dependency probe. Creation-time assembly means the generator *knows* whether analytics is present; the integration should be wired (or not) at generation time, not runtime-probed.

### TA10 (Medium) — `railway_utils.py` broad exception swallowing

`quickscale_cli/utils/railway_utils.py:469,534,774` (and narrower variants at `:52,:236`): `except Exception: return None` around URL extraction, variable parsing, and status queries. Callers cannot distinguish "not deployed yet" from "railway CLI crashed / output format changed," so deployment problems surface as silent `None`s in status output. The narrow `subprocess`-error catches for "is the CLI installed" probes are defensible; the broad `Exception` catches are not.

### TA11 (Low) — Invalid `PORT` silently coerced to 8000

`docker_utils.py:164-173` `get_port_from_env()`: `PORT` defaults to `"8000"` (acceptable dev convention, mirrors docker-compose) **but** a non-numeric `PORT` hits `except ValueError: return 8000` — a misconfigured value is silently replaced rather than reported. Also `generator/templates/Dockerfile.j2:160` healthcheck defaults PORT (consistent with Railway convention; note only).

### TA12 (Low) — Deprecated catalog compat delegates; fail-open readiness for unknown names

`contracts/module_catalog.py:128-175`: `get_module_names()` / `get_module_entries()` are documented "Deprecated since D2 … kept for backward compatibility only," yet still exported from the `contracts/__init__.py` public API with no F-EXCEPTION entry or sunset. Additionally `get_module_readiness_reason()` (`:270-289`) returns `None` for **unknown** module names — same return as "ready" — so readiness gating is fail-open for names the catalog has never heard of (mitigated only if all callers validate existence first).

### TA13 (Low) — Best-effort hash-capture step always succeeds

`apply/steps/wiring.py:71-120` `step_capture_hashes`: on `OSError` it prints a reporter warning but returns `StepOutcome(success=True)` — drift detection silently loses coverage while `quickscale apply` reports success. Deliberate design ("informational only"), but it is graceful degradation inside the apply pipeline. **Decision needed:** either fail the step (hash capture over files the apply itself just wrote should never fail) or register it as a documented F-EXCEPTION.

### TA14 (Low) — Mandated `# F-EXCEPTION:` tags absent from code

decisions.md §fail-hard-principle requires each documented exception to carry a `# F-EXCEPTION: <tag>` label in code. `grep -rn "F-EXCEPTION"` across all source returns **zero** hits. `_read_through_import_legacy` (`project_state.py:415`) mentions "F12.2" in its docstring but not in the mandated tag format, and the F12.2-adjacent legacy paths in `remove_command.py` (`_load_legacy_tracking`, legacy `config.yml` snapshot/update) are not listed in the exception table at all. Traceability drift between SSOT and code.

### TA15 (Low) — Dev-tooling silent parse failure

`scripts/check_module_core_compatibility.py:381-388`: `tomllib.load` wrapped in `except Exception: return None` — a malformed module `pyproject.toml` makes the compatibility checker silently *skip* that module instead of failing the check. A checker that silently skips broken inputs defeats its purpose.

---

## Notes (not violations, watch items)

- `orgs/public_context.py:140-144`: `except Exception: return None` on system-org lookup is **fail-closed** (tenant managers return `.none()`), so isolation is preserved — but a DB-level error renders as "no data" instead of a 500. Silent-but-safe; consider letting non-`DoesNotExist` errors propagate.
- DR engine (`dr_engine/*`) fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT` default `local`) are by-design recovery behavior, exempt per §fail-hard-principle scope.
