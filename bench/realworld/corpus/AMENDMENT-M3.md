# Amendment 1 — settled expenses become immutable

**Issued at the start of milestone 3. Supersedes the parts of `plan.md` it names.**

Finance flagged a problem with the milestone 2 design during review. Once money has
actually changed hands, editing the expense that money was based on rewrites history:
the settlement transfers no longer reconcile against the expenses that produced them,
and there is no record of what was originally agreed. Correcting a settled expense has
to leave a trail instead of overwriting one.

## The rule

An expense is **locked** once it has been covered by a settlement. A locked expense is
never modified and never deleted. Corrections to it are recorded as **adjustments**,
which carry into the next settlement round.

## Adjustment

```
Adjustment {
  id, expenseId, groupId, createdAt, createdBy,
  reason: "edit" | "reversal",
  deltaShares: [{ userId, deltaCents }]      // ascending userId
}
```

`deltaCents` may be negative and may be zero; zero entries are included so that every
user affected by either the old or the new shares appears exactly once.
`deltaShares` sums to the change in the expense's total.

## Changes to `plan.md`

**`PATCH /api/expenses/:expenseId`** — when the target is locked, the expense is not
touched (`updatedAt` does not move):
- 201 → `{ adjustment: Adjustment }` with `reason: "edit"`, where `deltaShares` is the
  share set the body *would* have produced minus the expense's current share set.
- 422 `VALIDATION` if the resulting share set would be invalid by the milestone 2
  rules, or if the body would change nothing.
- Permissions are unchanged.

Unlocked expenses behave exactly as milestone 2 specifies.

**`DELETE /api/expenses/:expenseId`** — when the target is locked:
- 201 → `{ adjustment: Adjustment }` with `reason: "reversal"` and `deltaShares` equal
  to the negation of the expense's current shares. The expense remains readable.

**`GET /api/expenses/:expenseId`** and the expense list gain `locked: boolean` and
`adjustments: [Adjustment]` (ascending `createdAt`).

**`GET /api/groups/:groupId/balances`** counts adjustments alongside expenses.

**Settlement** gains `coveredAdjustmentIds: [string]`, filled the same way as
`coveredExpenseIds`. An adjustment covered by a settlement is itself locked and cannot
be adjusted further. The preview must reflect uncovered adjustments — a group whose
only uncovered activity is an adjustment still previews transfers.

## Consequences for milestone 4

Carry these forward; they are part of milestone 4's definition of done.

- The audit log gains `action: "adjusted"` and `targetType: "adjustment"`. An
  adjustment writes one entry. A `PATCH` or `DELETE` against a locked expense writes
  the `adjusted` entry, **not** `updated` or `deleted`.
- The CSV export gains a leading `kind` column, `expense` or `adjustment`:

```
kind,expense_id,date,description,paid_by_email,participant_email,share_cents,settled
```

  Adjustment rows carry the adjusted expense's `expense_id`, the adjustment's own
  `date`, `description` of the form `Adjustment (<reason>)`, and `share_cents` equal
  to `deltaCents`. Rows remain ordered by date ascending, then `userId` ascending.
