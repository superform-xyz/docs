# Documentation checks

Requires Node 22, npm, Python 3.12+ and Bash. Development dependencies are pinned in `package-lock.json`; install with:

```sh
npm ci --ignore-scripts
```

## Regenerate indexes

```sh
npm run docs:index
npm run docs:index:check
```

`docs.json` is the navigation source. The generator walks `tabs`, `groups`, and nested `pages` in order. `root` is navigation metadata, not another page. Duplicate page entries and missing MDX files fail generation. Both outputs are assembled before either is written. No timestamps or network responses enter the generated files.

- `llms.txt`: every navigated MDX page, with its frontmatter title and description.
- `llms-full.txt`: the same pages in navigation order, with frontmatter removed and a title/source boundary per page.
- External `METHOD /path` entries: listed with their configured OpenAPI source, not treated as local MDX or silently dropped. The external schema is not embedded in the full corpus.
- `scripts/llms-preamble.txt`: maintained agent notes, including the pre-existing non-Operate notes. Edit this source, not the generated index.

Run generation again after parallel documentation edits are integrated. `--check` compares complete expected bytes, not merely route counts.

## Local MDX build and links

```sh
npm run docs:check
```

This runs Node tests, verifies both generated indexes, compiles every repository MDX file with `@mdx-js/mdx` and GFM support, and runs the public Python regression/harness suite. Frontmatter uses pinned `yaml` with a data-only core schema: alternate engine declarations, unresolved tags, duplicate keys and excessive aliases are rejected. It also checks:

- navigation targets and duplicates;
- the approved original Operate routes plus additions and six groups;
- Operate orphans;
- local Markdown/JSX links, images, static IDs, and heading fragments;
- fenced JSON syntax.

Compilation is in memory. It does not execute embedded application components, test a remote API, schema-validate strategy plans, or establish economic correctness. The public fixture suite is included in `docs:check`; real-engine validation remains a separate opt-in command. The hidden `build/manage-a-supervault.mdx` is compiled and link-checked but is not added to navigation or to the navigation-derived corpus.

## Mintlify platform checks

The inspected CLI exposes these commands:

```sh
npm exec --yes --package=mint@4.2.1076 -- mint validate --telemetry=false
npm exec --yes --package=mint@4.2.1076 -- mint broken-links --telemetry=false
```

These commands depend on the remote OpenAPI integration. The unsupported root-level `openapi` key has been removed; the navigation groups retain their explicit OpenAPI sources. This resolves the former `/docs.json` unsupported-version error (the CLI mistook the config for an OpenAPI document). Do not call local compilation a Mintlify platform-build pass. `mint validate --disable-openapi` is not equivalent: API-operation navigation entries can become missing-page warnings when generation is disabled. Re-run full validation against the integrated checkout rather than waiving that gate.

For an interactive local preview:

```sh
npm exec --yes --package=mint@4.2.1076 -- mint dev --no-open --telemetry=false
```

Use the URL printed by the CLI. The command does not log in, publish, or deploy. The preview can still warn about external schema generation; inspect the actual output rather than assuming success.

## Portable Operate verification

Requires Python 3.12+ (standard library only). From the repository root:

```sh
python3 -B -m unittest discover -s scripts -p test_operate_validation.py -v
python3 -B scripts/validate_operate.py
```

The public suite inventories **all 39 Operate pages**, including pages with no fences, using `fixtures/operate-snippet-inventory.json`. Every fence has an explicit classification and reviewed content hash. New/changed fences fail until a reviewer classifies them and adds the appropriate tests; do not blindly regenerate this inventory to turn a failure green. Backtick/tilde fences and Markdown indentation are recognized. Categories distinguish actual engine snippets, tested Python, public-read commands (offline `bash -n` only), API route/body notation, and illustrative JSON/text. All engine-classified fences must map to extracted compiler/schema fixtures. This is not a claim that API notation or placeholder creation requests were executed.

The suite checks repeated case-study deployment/position/strategy identifiers across all pages, label-to-ID/version/state mappings, AP/AF thresholds and targets derived from the captured rules, and exact published plan equality against the dated public capture. Unknown identifiers fail; historical intent/execution/fill/receipt identifiers are narrowly scoped to the trace page, and the separate pinned SMA source-test address is scoped to Variables. Synthetic teaching scenarios are kept separate from captured policy. It executes the monitoring classifier (10 cases) and audit poller (6 scenarios) with synthetic inputs. Regression tests mutate plans, identifiers, thresholds, versions, missing-telemetry classification, poller watermark and unclassified fences. The current fixture extraction prepares 22 compiler/schema snippets and 67 evaluator cases from 17 selected pages, including the complete same-asset refill. Without `--source`, engine checks are explicitly **SKIPPED**, not reported as passing. Run without Python optimization (`-O`/`PYTHONOPTIMIZE`), which disables assertions.

### Optional real-engine validation

Authorized engineers with an existing local `superman-strategy` checkout can run:

```sh
# Set to your existing checkout; this script never clones/fetches it.
export STRATEGY_SOURCE="$HOME/src/superman-strategy"
python3 -B scripts/validate_operate.py --source "$STRATEGY_SOURCE"
```

The checkout must contain commit `fc50b3ca5f1d66294e7476b1ff1088e92b126fbd`. Its current branch/HEAD and working-tree changes do not determine the tested source. The runner resolves that exact commit and uses `git archive` into a fresh temporary directory, then adds only `scripts/operate_docs_test.go`. It never checks out, modifies, or vendors engine source. Set `TMPDIR` to a writable scratch directory **outside** the source checkout if needed; each archive is removed on exit. No generated fixtures/manifests, engine archive, or operational logs are written into this repository.

The pinned engine declares Go **1.26.9**. Put that installed toolchain's `bin` directory first on `PATH` and prepopulate the module cache from that pinned `go.mod`/`go.sum` in a separately authorized isolated archive. A cached automatic toolchain can still fail with `checksum database disabled by GOSUMDB=off`; in that case invoke its installed binary via `PATH`, not by weakening the offline settings or editing the archived `go.mod`. Verify `go version` outside the source checkout. The runner sets `GOPROXY=off`, `GOSUMDB=off`, `GOWORK=off`, and `GOFLAGS=-mod=readonly`; it cannot download missing dependencies. A missing toolchain/module fails rather than substituting a mock evaluator. It does not load service credentials or start the application.

Engine mode runs:

- Actual compiler/validator/schema checks for 22 extracted JSON/numeric snippets.
- Actual high-precision evaluator checks for 67 scenarios, including zero/missing inputs, exact boundaries, dust, conversions, integer truncation, liquidity caps, and post-action states.
- Four captured AP0/AP1/AF0/AF2 configurations through config validation and simulation admission; AP1/AF2 must reject unsupported liquidity inputs.
- Negative syntax/alias cases in `operate_docs_test.go`.
- Five source-owned cooldown, occupied-concurrency, and stale-version tests. Required test names must appear as passed; a zero-match `go test` is a failure.

The harness proves the listed fixture behavior, not every prose claim, model fidelity, transaction feasibility, deployed binary parity, authenticated actions, or settlement. Synthetic snapshots are test inputs, not live measurements. It does not call production, send notifications, sign, or transact. Python snippets are executed as code from the reviewed checkout, so run it only in a trusted local environment or unprivileged CI without secrets.

### Fixture provenance

`scripts/fixtures/operate-public-2026-10-19.json` is a projection of the unauthenticated public-vault Strategy GET response captured at `2026-10-19T21:22:55Z`; its metadata contains the exact source URL, capture time, field selection, and engine pin. It includes four needed strategy configurations, the borrow action configuration used for plan parity, and ID/state/version metadata for eight other definitions named in the case-study table (labels are documentation labels, not rewritten source names). Unrelated strategy configurations and service/account/session material are not included. Preserve its historical meaning: updating it requires a new dated public capture and review, not assuming historical thresholds remain live policy.

### Public CI

`.github/workflows/docs-check.yml` runs `npm ci --ignore-scripts` and `npm run docs:check` (including the Python regression tests and public harness) on pull requests and main pushes. Only public package installation uses the network; validation does not fetch production APIs or external OpenAPI. The job has read-only repository permissions, does not persist Git credentials, and references no secrets or private engine source. The local MDX compiler is not a Mintlify platform build. Local passes do not establish that the hosted workflow or preview has run.

The `gray-matter` dependency and its `js-yaml` → `argparse` → `sprintf-js` advisory chain have been removed. The replacement parser has regression tests for safe frontmatter in both validation and index generation, including alternate JavaScript-engine declarations and executable YAML tags. `npm audit --ignore-scripts` returned zero vulnerabilities after this migration; rerun it when dependencies change. No force-fix or major downgrade was used.
