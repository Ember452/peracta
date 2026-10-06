# Peracta

**A persistent execution kernel for AI agents — what is done cannot be redone.**

English ｜ [中文](README.md)

> Resume from the crash point, side effects exactly once, and every run can be replayed byte for byte.
> Every step leaves evidence — not "we promise", but "this is what we observed".

## The target state

**V0.1 · single-machine kernel (once the plan is done):**

<video src="docs/assets/v01-target-panel.mp4" controls muted loop autoplay playsinline></video>

*The V0.1 target architecture. On the left, "crash drills" light up in turn: kill -9 → resume with zero re-runs, a repeated effect hits the claim cache, unknown states go to reconciliation. On the right, the L0–L5 layered kernel and the SQLite event journal. Animated numbers are simulated.*

**V1.0 · after all extensions:**

<video src="docs/assets/v10-vision-panel.mp4" controls muted loop autoplay playsinline></video>

*The V1.0 vision. Entry surfaces (Claude Code / Qoder / MCP / CLI / CI) → framework adapters → the zero-dependency sync kernel → pluggable storage backends → platform pieces (static scan / sandbox / human arbitration). deps=0 and dups=0 are the invariants shared by both panels.*

> Video not playing? See the stills: [V0.1](docs/assets/v01-target-panel.png) · [V1.0](docs/assets/v10-vision-panel.png)

## The problem: the AI-agent execution gap

What happens when an agent that edits data, sends email and spends money crashes and retries?

| Scenario | Consequence |
|---|---|
| Step 3 is killed with `kill -9`, the run restarts | Steps 1–2 fire their side effects again: duplicate refunds, duplicate emails |
| The effect was sent, the confirmation was not journalled, then a crash | Unknown state: did that refund actually happen? Nobody can say |
| A long-running agent fails and retries | Burn tokens and money all over again, with no audit trail |

Temporal / Restate give you "it won't re-run"; **Peracta gives you "proof that no duplicate side effect happened"** — via a fault-injection verifier that must first prove it can catch problems on a deliberately broken counterexample.

## The four promises

| # | Promise |
|---|---|
| 0 | **Only claim what was observed** — missing evidence is labelled, never dressed up as a health score |
| 1 | Completed steps are never re-run |
| 2 | Committed side effects happen exactly once |
| 3 | Every run can be replayed deterministically |

## The planned API (locked for V0.1, sync-first)

```python
from peracta import flow

@flow
def refund_agent(ctx):
    order = ctx.step("fetch_order")
    with ctx.effect(key=f"refund:{order.id}", reconcile=query_refund):
        gateway.refund(order)   # after a crash: committed effects are not re-executed
```

```bash
peracta run examples/refund_agent.py                        # A1 runs clean
peracta resume <run-id>                                     # A2 after a crash: done steps are skipped
peracta replay <run-id>                                     # A5 byte-identical replay
peracta verify examples/refund_agent.py --fault crash --at every-step --repeat 50
                                                            # A3 duplicate side effects must be 0
```

> ⚠️ These are the locked V0.1 target interfaces. `run` / `resume` are implemented (see the status table below and `examples/`); `effect` / `replay` / `verify` belong to T4 / T5 and are not implemented yet.

## How it relates to existing work

| | Temporal / Restate | LangGraph / crewAI | actenon-scan | Peracta |
|---|---|---|---|---|
| Done steps are not re-run | ✅ | partial | — | ✅ |
| Side effects exactly once | DIY | ❌ | — | ✅ |
| Deterministic replay of a whole run | workflow code only | ❌ | — | ✅ |
| Fault injection proving "no duplicates" | ❌ | ❌ | static scan | ✅ |
| Zero runtime dependencies | ❌ | ❌ | ✅ | ✅ |

## Engineering constraints (hard ones)

- **Zero runtime dependencies**: Python 3.13 standard library; storage via stdlib `sqlite3`
- Zero-dependency is a **test assertion**, not a README slogan (enforced in `tests/architecture/`)
- One-way layering (L0–L5), enforced by tests; docs stay in sync with code; decisions are recorded two-tier (changelog + ADR)

## Status

**The durable kernel and its CLI have landed (plan one complete), with hard-kill resume verified end to end. V0.1 remains: effect idempotency (T4) and fault-injection verification (T5).**

| Task card | Scope | Status |
|---|---|---|
| T1 | Skeleton: pyproject / src / pytest / ruff / CI | ✅ |
| T2 | SQLite event journal (runs / events; claims deferred to T4 by plan) | ✅ |
| T3 | Step recording + resume skipping done steps | ✅ |
| T4 | Effect idempotency (claim first) + reconcile for unknown states | ⬜ |
| T5 | verify fault injection + the deliberately broken counterexample | ⬜ |

Done: four spec documents, target-state panel diagrams, collaboration guidelines; the kernel layers `@flow` / `Context.step` / resumable `execute`, the SQLite event journal, the CLI (run / resume / ps), architecture guards and 103 tests (including an end-to-end hard-kill resume run).

## Documentation

| Document | Scope |
|---|---|
| [PROJECT.md](docs/PROJECT.md) | **Constraints**: what V0.1 does, does not do, and how it is accepted (A1–A6) |
| [FEATURES.md](docs/FEATURES.md) | **Map**: the whole idea, no trade-offs taken |
| [STRUCTURE.md](docs/STRUCTURE.md) | **Structure**: layout, layers, dependency direction |
| [EXTENSIONS.md](docs/EXTENSIONS.md) | **Extensions**: future directions (incl. borrowing lists from actenon-scan / better-harness) |

## License

MIT. Panel animations generated with the [live-panel skill](https://github.com/ythx-101/live-panel-skill); configs and videos live in [docs/assets/](docs/assets/).
