# Plan only — the integration test is not implemented

## Goal

A self-contained integration test of a Dekopon agent modifying its own configuration through native `gh` commands, committing changes to this repository, and observing itself reconfigure through Argo CD. GitHub Actions starts the experiment through `workflow_dispatch`, bootstraps kind and Argo CD, and uses this repository as an Argo app-of-apps.

The broader owner goal is an agent “driving itself until it's up.” The proposed first scenario below is narrower: an already-working seed agent changes reloadable configuration. That narrowing is a proposal, not an owner requirement to exclude restart or deployment-repair scenarios.

## Decisions and provisioned resources

- Organization: https://github.com/dekopon-agents-integration-testing — GitHub Free, personally owned.
- Repository: https://github.com/dekopon-agents-integration-testing/self-configure — public.
- The owner explicitly authorized implementing the harness directly on `main`.
- Organization-owned GitHub App: `dekopon-integration-self-configure`, App ID `5550939`.
- Installation ID: `177097001`, selected repository `self-configure` only.
- App permissions: Contents read/write and Metadata read; webhooks disabled.
- OpenRouter workspace: Scientist.com / Default Workspace.
- OpenRouter key name: `dekopon-agents-integration-testing-self-configure`; workspace-owned, $10 total non-resetting limit, no expiration.
- Proposed model: `openai/gpt-6.1-terra`; no silent model fallback.

Organization Actions secrets, each restricted to this repository:

| Name | Purpose |
| --- | --- |
| `SELF_CONFIGURE_APP_PRIVATE_KEY` | Broker-side GitHub App authentication |
| `OPENROUTER_API_KEY` | Model-client authentication |

Organization Actions variables, likewise restricted to this repository:

| Name | Value |
| --- | --- |
| `SELF_CONFIGURE_APP_ID` | `5550939` |
| `SELF_CONFIGURE_APP_INSTALLATION_ID` | `177097001` |

Credential values are not stored in Git. Temporary credential-transfer files were removed after organization-secret storage was verified. No workflow, cluster, or paid inference test has run.

## Blocking prerequisite: native repository file writes

At assessment, `dekopon-provider-gh` main and its latest release, `v0.12.0`, lacked repository file writes. Its `gh` command is a bounded native provider interface, not the full upstream CLI; arbitrary `gh api` writes are intentionally unavailable.

A planner assessed the missing capability and drafted the following task. **This specific task has NOT been added to the diaphanous epoch queue, implemented, or released.** Do not mistake the draft for scheduled work.

> Add native `gh.content.commit` and a `gh repo commit-files` command for bounded file creates, replacements and deletions, published as one visible atomic multi-file commit. Require an explicit repository, branch and expected head SHA; enforce owner-defined repository/branch/path restrictions. Preserve broker-only credentials, reject conflicts without automatic retry, and exclude arbitrary API passthrough. Test authorization, bounds, concurrency, failure behavior and the real Wasm component's HTTP requests.

Implementation details remain for the provider owner to settle. In particular, verify the actual GitHub API concurrency contract: a non-force ref update must not be described as a strict compare-and-swap without proof. Avoid sequential file writes that expose partially updated configuration. The planner suggested 1–16 UTF-8 files, 64 KiB per file and 256 KiB total as provisional bounds, not settled public contracts.

The existing private campaign-trail epoch is `store/epochs/diaphanous-dilettantes/`, with related work under `21-gh-parity/`. Its parity inventory already plans PR/issue creation and editing, releases, secrets and repository administration. Do not duplicate those tasks; none is required for this first scenario.

Build and release the new provider in its owning source repository, then consume a pinned version and checksum here. This repository must not clone and compile upstream source as its artifact-production mechanism.

## Proposed first scenario

```text
workflow_dispatch
  -> fixed CI driver
  -> kind + pinned Argo CD
  -> credentials + root Application
  -> working seed Dekopon agent
  -> authenticated task delivery
  -> agent commits its own configuration on a run branch
  -> Argo applies that exact commit
  -> gateway activates the new configuration
  -> fresh invocation demonstrates changed behavior
  -> independent verdict, evidence upload, cleanup
```

### Fixed bootstrap

CI owns cluster creation, credential injection, root/child Application definitions, broker authority, initial agent configuration, verification and cleanup. The agent cannot bootstrap itself from a state where it cannot run.

Use published, compatible Dekopon image/chart/provider artifacts pinned by version and digest/checksum. Keep gateway and broker process/credential separation intact. Inject the App credential only into the broker's supported credential path; the OpenRouter key belongs only to the model client.

The root Application and all child sources for a run must resolve to the intended run branch. CI creates `runs/<run-id>-<attempt>` from a recorded baseline. Harness development occurs on `main`, but experimental agent commits do not accumulate there and make later runs start already configured.

### Writable surface

Initially permit only a small agent/catalog configuration surface. Keep CI workflows, test assertions, broker grants, credentials, Argo projects, Application definitions, RBAC and arbitrary workloads out of the agent's writable paths.

GitHub App Contents write is repository-wide, not a path restriction. Enforce the narrower boundary in the provider/broker and protect the harness branch separately. Unrestricted Argo manifest writes could deploy a workload that reads Kubernetes Secrets; merely hiding credentials from the prompt is not sufficient.

### Trigger and reconciliation

CI delivers an authenticated initial event locally, using the supported gateway transport and a port-forward as appropriate. This exercises event admission and the agent, but does not prove GitHub's outbound webhook delivery. A real GitHub webhook into kind would require a reachable endpoint/tunnel and is not part of this first scenario.

Argo reconciles Git to Kubernetes. Gateway catalog/agent configuration supports hot reload; broker configuration and some gateway fields require a restart. Select one genuinely reloadable setting with an independently observable behavioral consequence during implementation.

Do not count a current model turn saying it changed as evidence of activation. After observing reconciliation/activation, CI delivers a fresh challenge. CI may provide bounded observations or follow-up triggers, but must not author the agent's corrective configuration.

### Independent pass criteria

All of the following must hold:

1. The seed configuration does not satisfy the target behavior.
2. The agent produces a permitted configuration change through the native provider.
3. Git records the expected commit and no out-of-scope changes.
4. Argo applies that exact commit, not merely some healthy revision.
5. The running gateway activates the changed configuration.
6. A fresh invocation demonstrates the target behavior.

Neither an agent's “done” message, Argo `Synced`, nor pod readiness alone is a passing result. The verifier runs from the fixed trusted harness, never from agent-modified test code on the run branch.

No other missing agent powers are currently known for this narrow scenario: repository reads already exist, CI creates branches and triggers turns, and Argo applies the changes. The agent needs no PR creation, secret management, Kubernetes administrator access or Actions dispatch permission. Runtime integration remains untested; this is not a claim that no further defects will be found.

## Proposed repository layout

```text
.github/workflows/self-configure.yml
bootstrap/                 # fixed root Application and restricted AppProject
apps/                      # fixed child Application definitions
config/seed/               # initially working agent
config/mutable/            # narrowly permitted self-modification surface
tests/                     # driver and independent assertions
```

Exact paths and implementation language are not yet chosen. Keep the harness small rather than creating a general orchestration framework.

## Bounds, evidence and cleanup

Proposed initial limits:

- Manual dispatch only; no recursive workflow launches from agent commits.
- One run at a time.
- Twenty-minute overall timeout.
- At most three agent-authored correction commits.
- Explicit model-step, tool-call and output limits.
- Stop on credit exhaustion, denied writes or unrecoverable bootstrap failure.

The OpenRouter $10 cap is a total spending allowance against workspace credit, not a separately funded wallet or a GitHub Actions budget. No top-up or larger budget is implied.

Upload bounded, sanitized evidence on success and failure: baseline and resulting SHAs, config diff, artifact pins, Argo applied revision, reload records, challenge results, trace references and available model usage. Do not upload Secrets, private keys, tokens or credential-bearing environment dumps.

Always destroy the task-owned cluster and stop tunnels/forwarders. Preserve failed-run evidence before cleaning up temporary branches. Do not automatically retry until green or substitute an infrastructure pass for agent success.

## Implementation sequence

1. Add the file-commit task to the existing epoch, settle its contract, implement and release it in `dekopon-provider-gh`.
2. Implement the fixed CI/bootstrap harness on this repository's `main`, using `workflow_dispatch`.
3. Prove deterministic reconciliation with a CI-authored fixture change. Label this infrastructure validation, not the agent test.
4. Replace the fixture writer with Terra using the released native `gh` capability; keep the same independent verifier.
5. Run the real bounded experiment and record actual results, failures and spending.
6. Decide the next scenario against the broader self-bootstrap goal.

## Broader requested goal not yet covered

The owner wants an agent driving itself until it is up. The first scenario does **not** yet demonstrate:

- Repair of an initially broken deployment.
- Restart-required reconfiguration and continuation after restarting itself.
- Arbitrary app-of-apps or workload changes.
- Real external GitHub webhook delivery into the ephemeral cluster.

The first three require an explicit follow-on design for authority, restart/continuation, observations and independent success criteria. They were narrowed out by the proposed first test, not rejected by the owner. External webhook delivery is an optional additional transport test, not a necessary condition of self-configuration.

## Resume checklist

- Recheck actual repository, provider release and epoch queue state; this document is a checkpoint, not live status.
- Confirm the dedicated OpenRouter key still has allowance and the GitHub App installation still targets only this repository.
- Ensure the native file-commit task is genuinely queued before claiming it is.
- Preserve the distinction between provisioned credentials, implemented infrastructure and a proven agent-driven passing run.
