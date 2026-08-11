---
name: steerable-testing
description: Plan tests with the user before writing them. Use when creating, expanding, or repairing tests where the user should be able to inspect coverage, challenge missed edge cases, and steer scope.
---

# Steerable Testing

Keep user in loop before writing tests.

## Rule

Do not write test code until user approves test plan.

Exception: user explicitly asks to skip review.

## 1. Inspect

Read enough code, existing tests, types, docs, and call sites to understand behavior and existing conventions.

Do not optimize for coverage %. Optimize for meaningful behavior.

If expected behavior is unclear, expose ambiguity. Do not guess silently.

## 2. Show test surface

Before proposing tests, show a compact review of relevant cases.

Use only dimensions that matter:

- happy path
- failures
- boundaries: empty/null/zero/max/before/at/after
- repeated calls, retries, idempotency
- partial failure
- ordering/concurrency
- timeouts/time boundaries
- malformed or unexpected data
- auth/permissions
- dependency failure or bad responses

Format:

```text
Test surface

Plan to test
- ...

Considered, not testing
- ... — reason

Possible gaps / questions
- What if ...?
- Should ... behave differently when ...?
```

Make omissions visible. User should be able to say:

- `you missed X`
- `what if Y?`
- `did you consider Z?`
- `why aren't we testing X?`

Never dump chain-of-thought. Show conclusions and assumptions only.

## 3. Propose tests

Give each proposed test an ID.

```text
T1 — expired token is rejected
Case: expires 1s before current time
Proves: expired credentials cannot reach handler
Level: integration
Boundary: real middleware, fake clock
```

For each test include only:

- exact case
- what it proves
- test level
- important fake/mock/real boundary, if any

Enough detail to judge test. No implementation noise.

## 4. Let user steer

Accept natural feedback or commands:

```text
approve
approve T1 T3
drop T2
change T3: ...
add: ...
you missed: duplicate requests
what if: write succeeds, response times out
why not test: concurrent calls
no mocks for T1
```

When user raises new edge case, revise test surface + proposal first. Do not jump straight to code.

## 5. Implement approved scope

After approval:

- write approved tests only
- follow repo conventions
- test observable behavior, not internals
- avoid unnecessary mocks
- do not add surprise tests

If implementation reveals materially different behavior, boundary, setup, or scope, stop and show only delta for approval.

```text
Plan delta
T2 needs real DB fixture; mocking ORM would test internals.
Recommendation: make T2 integration test.
Approve?
```

## 6. Run and report

Map result back to IDs.

```text
T1 PASS
T2 PASS
T3 FAIL — product behavior differs from approved expectation
```

Distinguish:

- test bug
- product bug
- ambiguous behavior
- environment/fixture problem

Do not change production code merely to make test pass unless asked.

## Done means

Before implementation, user can answer:

- What are we testing?
- Which edge cases were considered?
- What are we intentionally not testing?
- What might still be missing?
- What will each test prove?
