# Independent self-configuration experiment

Resumed by Xavier on 2026-11-03. The native write prerequisite shipped in
[gh provider v0.13.0](https://github.com/dekopon-agents/dekopon-provider-gh/releases/tag/v0.13.0),
including [PR 44](https://github.com/dekopon-agents/dekopon-provider-gh/pull/44).
The published gh-provider.wasm SHA-256 is
`8fe93ef36199e3689f7a260c505343beb9dd4b7a8c0b0edaa3f5adadd7d3ceed`.
Its released skill and disabled policy example were read before implementation.

The manual workflow creates an isolated kind cluster and run branch. A working
Terra agent reads and updates one configuration file through native gh. Argo
reconciles the observed commit and the gateway reloads it. A separate verifier
principal sends a new nonce in a new conversation and checks the changed prefix.
Only the trusted baseline runs assertions. CI fixture commits never count as
agent success. Runtime bounds and artifact pins live in the workflow and driver.
The three-call configuration-turn limit permits at most three writes; challenge
principals cannot write. Unknown write outcomes require a state read.

GitHub App dekopon-integration-self-configure (5550939), installation 177097001,
is selected only for this repository. Its private key and the OpenRouter key
remain repository-selected organization secrets. The intended model is
openai/gpt-6.1-terra, with no fallback, under the existing $10 non-resetting cap.
The workflow checks allowance before inference and records allowance afterward.
No new credentials or budget are authorized.

The evidence artifact is the run receipt, including failed verdicts. A single
manual run is authorized; preserve its outcome without automatically rerunning.
Restart survival, broken deployment repair, arbitrary workload changes and real
external webhook delivery remain follow-ons. No RPi deployment is involved.

## First run receipt

[Run 41755414870](https://github.com/dekopon-agents-integration-testing/self-configure/actions/runs/41755414870)
tested `5b42ab2243f04d4f125261b21cbea5ac3c8f6be4` and failed before inference.
Kind and Argo bootstrap completed. CI created fixture commit
`31fea007f57ecf4b1adb53ec9f04b9275e0f8bbc`; the driver immediately queried
the not-yet-created catalog Application and aborted on NotFound.
No agent-authored commit, applied candidate, activation or fresh-turn success
was observed. OpenRouter usage remained $0, with $10 remaining and no reset.
The sanitized evidence artifact includes the failure and spending receipts.
Cluster, run branch and Docker network cleanup completed; the App token was
revoked by the token action's post step.

The polling fix treats an absent child as pending while retaining the bounded
deadline. Regression tests cover absence and exact revision matching. This fix
has local validation only; no second dispatch was performed.

## Second run receipt

Xavier authorized another attempt with the polling fix.
[Run 41757162939](https://github.com/dekopon-agents-integration-testing/self-configure/actions/runs/41757162939)
tested `173b5a21fa49245d0001b9ccae8b67f48c36ce08`. Argo created its child
Applications and the catalog reconciled fixture commit
`2b6ed92368074f781ae894bb647d03b842b60658`. The broker refused startup because
its provider emptyDir retained unprotected group/world writes on `/providers`.
The deployment rollout timed out. No model invocation, agent commit or activation
was observed. Usage remains $0, with $10 available. Cluster, branch and network
cleanup completed and the App token action's post step succeeded.

The init container now makes the provider directory broker-owned and 0700. It
also prepares the gateway's shared temporary directory as gateway-owned and
0700, as required by the local transport socket admission check. These filesystem
fixes have local validation only; no third dispatch was performed.
