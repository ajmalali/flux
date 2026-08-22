# Ledger — shared expense tracking for small teams

A web service where a group of people record shared expenses and settle up. Four
milestones. Each is a separate work session and is reviewed before the next begins.

## Stack (fixed)

- Next.js (App Router), TypeScript, React.
- SQLite via `better-sqlite3`. One file at `data/ledger.db`. Migrations live in
  `db/migrations/` and run via `npm run db:migrate`.
- Vitest for unit and route tests, Playwright for browser tests.
- `npm run dev` (port from `PORT`, default 3000), `npm test`, `npm run build`.

## Rules that hold everywhere

**Money is integer cents.** No floats anywhere in storage or arithmetic. Amounts are
positive integers. A response never contains a fractional amount.

**Rounding.** Whenever a total must be divided and does not divide evenly, each share
is `floor(share_exact)`, and the leftover cents are distributed one each to
participants in ascending `userId` order until exhausted. This rule is used
identically by every split strategy. Shares always sum to exactly the total.

**Errors.** Every non-2xx response has body `{ "error": { "code": "...", "message": "..." } }`.
Codes used below: `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `NOT_FOUND` (404),
`VALIDATION` (422), `CONFLICT` (409). `message` is human-readable; nothing asserts on it.

**Auth.** Session cookie named `ledger_session`, HttpOnly, SameSite=Lax. Any endpoint
under `/api` other than `/api/auth/register` and `/api/auth/login` returns 401
`UNAUTHENTICATED` without a valid session.

**Timestamps** are ISO-8601 UTC strings with `Z`, e.g. `2026-01-31T12:00:00.000Z`.

**Ids** are strings. Their format is not specified.

---

# Milestone 1 — accounts and groups

## Endpoints

### `POST /api/auth/register`
Body `{ email: string, password: string, name: string }`.
- 201 → `{ user: { id, email, name } }`, and sets the session cookie.
- 422 `VALIDATION` if email is not of the form `x@y.z`, password is under 8
  characters, or name is empty.
- 409 `CONFLICT` if the email is already registered (case-insensitive).

Passwords are never stored in plaintext and never appear in any response.

### `POST /api/auth/login`
Body `{ email: string, password: string }`.
- 200 → `{ user: { id, email, name } }`, sets the session cookie.
- 401 `UNAUTHENTICATED` on wrong email or password. The two cases are indistinguishable.

### `POST /api/auth/logout`
- 204, clears the session cookie.

### `GET /api/auth/me`
- 200 → `{ user: { id, email, name } }`.

### `POST /api/groups`
Body `{ name: string }`.
- 201 → `{ group: { id, name, createdAt, members: [{ userId, name, email, role }] } }`.
  The creator is a member with `role: "owner"`.
- 422 `VALIDATION` if name is empty or longer than 100 characters.

### `GET /api/groups`
- 200 → `{ groups: [{ id, name, createdAt, memberCount }] }` — only groups the caller
  is a member of, ordered by `createdAt` descending.

### `GET /api/groups/:groupId`
- 200 → `{ group: { id, name, createdAt, members: [{ userId, name, email, role }] } }`,
  members ordered by `userId` ascending.
- 404 `NOT_FOUND` if the group does not exist **or** the caller is not a member. A
  non-member must not be able to tell the two apart.

### `POST /api/groups/:groupId/members`
Body `{ email: string }`. Owner only.
- 201 → the same shape as `GET /api/groups/:groupId`.
- 403 `FORBIDDEN` if the caller is a member but not the owner.
- 404 `NOT_FOUND` if no user has that email.
- 409 `CONFLICT` if that user is already a member.

New members have `role: "member"`.

### `DELETE /api/groups/:groupId/members/:userId`
Owner only.
- 204 on success.
- 403 `FORBIDDEN` if the caller is not the owner, or if the target is the owner
  (an owner cannot be removed).

## UI

- `/register` and `/login` — forms; on success redirect to `/groups`.
- `/groups` — the caller's groups, and a form to create one.
- `/groups/[groupId]` — group name and member list, and (for the owner) a form to add
  a member by email.

## Done when

`npm test` passes, `npm run build` succeeds, and the flows above work in a browser.

---

# Milestone 2 — expenses and splits

An expense is money one member paid on behalf of some members of the group.

## Shape

```
Expense {
  id, groupId, description, amountCents, paidBy,        // paidBy = userId
  splitStrategy: "equal" | "exact" | "percentage",
  shares: [{ userId, amountCents }],                     // ascending userId
  createdAt, updatedAt
}
```

`shares` always sums to exactly `amountCents`, whatever the strategy.

## Endpoints

### `POST /api/groups/:groupId/expenses`
Body:
```
{ description: string,
  amountCents: integer,
  paidBy: string,
  splitStrategy: "equal" | "exact" | "percentage",
  participants?: string[],        // equal only
  shares?: [{ userId, amountCents }],   // exact only
  percentages?: [{ userId, basisPoints }] }  // percentage only
```
- 201 → `{ expense: Expense }`.
- 422 `VALIDATION` if: description is empty; `amountCents` is not a positive integer;
  `paidBy` is not a group member; any listed participant is not a group member; the
  strategy's own field is missing; or a duplicate `userId` appears in the list.

Per strategy:

- **equal** — `participants` is a non-empty list of member ids. The total is divided
  by the rounding rule above. If `participants` is omitted, every current group member
  participates.
- **exact** — `shares` must sum to exactly `amountCents`, else 422 `VALIDATION`. Every
  share must be a positive integer.
- **percentage** — `percentages` are integer basis points and must sum to exactly
  `10000`, else 422 `VALIDATION`. Each share is `floor(amountCents * basisPoints / 10000)`,
  then the rounding rule distributes the remainder.

### `GET /api/groups/:groupId/expenses`
- 200 → `{ expenses: [Expense] }`, ordered by `createdAt` descending, then `id` ascending.
- Supports `?paidBy=<userId>` and `?participant=<userId>` filters, combinable (AND).

### `GET /api/expenses/:expenseId`
- 200 → `{ expense: Expense }`. 404 `NOT_FOUND` if the caller is not a member of the
  expense's group.

### `PATCH /api/expenses/:expenseId`
Body: any subset of the create body. Recomputes shares from the resulting state.
- 200 → `{ expense: Expense }` with `updatedAt` advanced.
- Same validation as create.
- 403 `FORBIDDEN` unless the caller is the payer or the group owner.

### `DELETE /api/expenses/:expenseId`
- 204. Payer or group owner only, else 403 `FORBIDDEN`.

### `GET /api/groups/:groupId/balances`
- 200 → `{ balances: [{ userId, netCents }] }`, ascending `userId`, **every current
  member present including zeroes**.

`netCents` is positive when the group owes the member, negative when the member owes
the group. Across a group the values sum to exactly `0`.

## UI

- `/groups/[groupId]` gains an expense list, an "add expense" form supporting all
  three strategies, and a balances panel.

---

# Milestone 3 — settling up

A settlement records that money actually changed hands and closes out the balances
it covers.

## Shape

```
Settlement {
  id, groupId, createdAt, createdBy,
  transfers: [{ fromUserId, toUserId, amountCents }],
  coveredExpenseIds: [string]
}
```

### `GET /api/groups/:groupId/settlements/preview`
- 200 → `{ transfers: [{ fromUserId, toUserId, amountCents }] }`.

Computed from the current balances. Requirements, in priority order:

1. Every transfer amount is a positive integer, and applying all transfers brings
   every member's balance to exactly zero.
2. **The number of transfers is minimal** for the current balances.
3. Ties are broken deterministically: the same balances always yield the same list,
   ordered by `fromUserId` ascending, then `toUserId` ascending.

An all-zero balance sheet previews `[]`.

### `POST /api/groups/:groupId/settlements`
- 201 → `{ settlement: Settlement }`. Records the current preview, and marks every
  expense that contributed to those balances as covered.
- 409 `CONFLICT` if the current preview is empty.

### `GET /api/groups/:groupId/settlements`
- 200 → `{ settlements: [Settlement] }`, `createdAt` descending.

After a settlement, `GET /balances` reflects only activity not yet covered.

## UI

- `/groups/[groupId]/settle` — the preview as a readable list of "A pays B $X", and a
  button to record it. Past settlements are listed.

---

# Milestone 4 — audit and export

### `GET /api/groups/:groupId/audit`
- 200 → `{ entries: [{ id, at, actorUserId, action, targetType, targetId, summary }] }`,
  `at` descending.

`action` is one of `created`, `updated`, `deleted`, `settled`. `targetType` is one of
`group`, `member`, `expense`, `settlement`. Every state-changing operation across
milestones 1–3 writes exactly one entry. Audit entries are never edited or deleted.

Group members may read the audit log. `?action=` and `?targetType=` filter it.

### `GET /api/groups/:groupId/export.csv`
- 200, `Content-Type: text/csv`, one header row, then one row per expense share:

```
expense_id,date,description,paid_by_email,participant_email,share_cents,settled
```

Ordered by expense `createdAt` ascending, then `userId` ascending. `settled` is
`true`/`false`. Fields containing a comma or quote are quoted per RFC 4180.

### Permission hardening

Audit every endpoint from milestones 1–3 against this table and fix what does not
match it. This is expected to find real gaps.

| actor | may |
|---|---|
| non-member | nothing; every group-scoped route is 404 `NOT_FOUND` |
| member | read the group, its expenses, balances, settlements, audit, export; create expenses; edit or delete **their own** expenses; create settlements |
| owner | everything a member may, plus add/remove members, and edit or delete **any** expense |

## UI

- `/groups/[groupId]/audit` — the log, filterable by action.
- A download link for the CSV export on the group page.

---

# Not specified — your call

Database schema, module layout, how split strategies are structured, transaction
boundaries, concurrency handling, error-message wording, styling, and anything the
UI needs beyond the pages named above.
