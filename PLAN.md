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
