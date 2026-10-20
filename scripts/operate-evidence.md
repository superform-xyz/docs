# Operate verification record

Scope: SUP-21556, curator operating documentation. This record describes the source and evidence boundaries for the upgrade, not certification of a production deployment.

## Source revisions

| Component | Revision | Reviewed surface |
|---|---|---|
| Strategy Engine | `fc50b3ca5f1d66294e7476b1ff1088e92b126fbd` | Compiler/evaluator, field adapters, plan validation, lifecycle/publication gates, simulation and API schemas |
| OMS | `bf36ed9fb23a640c34943544f824ff4f5fb77939` | Plan execution/output propagation, session readiness and API schema |
| SuperformOS frontend | `b782f601be8c29b5258fc9a2ed02f71209ee5c37` | Rule editor, BFF session/public-read boundaries, permissions, simulations and Intent History |
| Frontend delta check | `d4b23acc778868eb9abe92d5d9dfa96a89e914cc` | No changes to cited auth/strategy/session/yield-source files relative to the original inspection |
| Management API | `927a803d27c4df4575e02adaf472f8f94b0db9ed` | Current OpenAPI, RBAC, compact Merkle definitions and mapped-history behavior |
| Management implementation baseline | `70dcf5126ec5aed70481dba5993df50c5b42c2b5` | Settings, audit storage/pagination and activation exemptions; relevant policy subsequently checked at the current management revision |
| v2-periphery | `300272085fd5a8c3b0a28ed91f154e53240a106d` | Manager assignment/replacement, pause, minimum-update-interval and hook-authorization boundaries |

These repositories may require organization access. Pin checks and isolated archives avoid modifying source checkouts. Source review does not establish deployed-bytecode parity.

## Historical case study

The canonical public fixture is `scripts/fixtures/operate-public-2026-10-19.json`. Its provenance identifies the public GET and capture time, `2026-10-19T21:22:55Z`. It is historical configuration, not current deployment truth or proof of the exact configuration that produced an earlier execution.

The AP1 worked investigation uses intent `99a5081e-9975-4cc9-82ec-fac97f355bc5` and Base transaction `0x100e0ae81927d2141d2a9d65b342c8e900fedd37e8c32eea195117e2681a8a2f` at block `52807073`. Detail/fills and the receipt were read without signing. Receipt-local share and token flows are documented; before/after loan balances, interest, residuals and resulting LTV are not fully reconciled.

## Verification layers

Run the commands in [scripts/README.md](README.md) from a clean checkout.

- Public checks validate navigation, generated indexes, data-only frontmatter, MDX syntax, local links/fragments/assets and documented fixture extraction. These do not execute the engine.
- Optional pinned-source verification runs the actual compiler/evaluator, schema checks, synthetic boundary cases and named publication/API gates in an isolated engine archive. A skipped private-source suite is not a pass.
- Mintlify platform validation checks the actual site configuration and API integration; local MDX compilation is not a substitute.
- Rendered preview checks cover the Operate landing, carry guide, execution plans and Intent History, including narrow-viewport behavior. The generated API playground is checked separately without invoking its requests.

Synthetic rule tests do not establish usable live feeds, execution liquidity, authorization, a successful transaction or a resulting LTV. Simulation admission does not establish an implemented loan-position transition.

## Review corrections

Independent source review distinguished minimum-update-interval proposal/cancellation, manager-gated API execution preparation and permissionless matured contract execution. It also separated public-vault analytics policy from authenticated audit access and BFF routing.

Independent delivery review required a portable harness, a data-only frontmatter parser, complete snippet classification and canonical case-study checks, explicit editor-unit mapping, and concrete recovery/funding procedures. The final PR should be reviewed against these changes rather than the initial implementation's passing tests alone.

## Platform configuration

The redundant root-level `docs.json.openapi` key made Mintlify 4.2.1076 classify the site configuration itself as an OpenAPI document. The supported navigation-group references already provide the specification. Removing only that root key preserves the parsed configuration, all five API groups and their 15 operation entries. Full validation passes with OpenAPI enabled; disabling it is not the fix.

## Unperformed actions

No authenticated create/save, simulation POST, session grant/rotation, root publication, signing, production strategy activation, funds movement or deployment was performed for this documentation release. Those procedures are source-reviewed, not live-rehearsed. The PR does not introduce a persistent unwind mechanism, a universal market-hours guard or a guarantee that automation reaches an LTV target.
