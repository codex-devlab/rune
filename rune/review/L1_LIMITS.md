# L1 Limits

L1 is a high-precision lexical pre-filter. It catches modal+verb+object polarity conflicts but misses semantic structure.

## What L1 catches

- Polarity opposition on the same (verb, object): "Always use X" vs "Never use X"
- Modal-strength when paired with negation: "Must do Y" vs "Do not do Y"

## What L1 misses

| # | Failure mode | Example | Why L1 misses |
|---|---|---|---|
| 1 | Negation via prepositional phrase | "Ship without running tests" vs "Always run tests before shipping" | No shared (verb, object) — "ship without" doesn't extract as `run tests` |
| 2 | Conditional scoping | "Use JS for prototype branches" vs "Use TS on main" | Both positive; scope is implicit, not lexical |
| 3 | Modal strength differences | "Must use Tailwind" vs "Should use Tailwind" | L1 v1 ignores strength gradient when both positive |
| 4 | Object aliasing | "useEffect" vs "effect hooks" | No token overlap on object |
| 5 | Subject scoping | "Frontend must use Tailwind" vs "Components should use CSS modules" | Subject hierarchy unknown to L1 |

For modes 1–5, run `rune review --l2` (Phase 3) — NLI cross-encoder verification.
