# Pipeline Operations Policy

## Preserve Useful Work

Pipeline runs and human changes may overlap. Do not cancel a healthy run only
because newer code or another useful commit exists.

The default response to divergence is:

1. Let useful work finish.
2. Fetch the latest `main`.
3. Rebase the publishing commit onto `main`.
4. Reconcile generated artifacts product by product when Git cannot merge them.
5. Validate the reconciled result before pushing.

Cancellation is reserved for runs that are stuck, repeatedly making no
progress, producing known-corrupt data, or competing with another active
writer.

## Conflict Resolution Rules

Never resolve generated JSON conflicts by blindly choosing all of `ours` or
all of `theirs`.

Preserve both kinds of work:

- Keep newer pipeline code, workflow definitions, validators, and tests.
- Keep newly completed valid product artifacts produced by a pipeline run.
- For the same product, prefer the newest result that passes validation and
  has the highest classification completeness.
- Preserve `review` and `insufficient_sources` reasons and quality metrics.
- Do not replace a complete valid result with an incomplete or invalid result
  solely because its file timestamp is newer.
- Do not include unrelated local files such as `sentiment-analysis/scratch/`.

Files requiring semantic reconciliation include:

- `sentiment-analysis/pipeline_state.json`
- `sentiment-analysis/needs_manual_review.json`
- `sentiment-analysis/product_registry.json`
- `sentiment-analysis/raw_comments/*.json`
- `sentiment-analysis/batches/**/*.json`
- `sentiment-analysis/classified/*.json`
- `src/data/*.json`

## Publish Procedure

Before publishing local pipeline changes:

```powershell
git fetch origin main
git rebase origin/main
python sentiment-analysis/tests.py
git diff --check
git push origin main
```

If rebase reports generated-artifact conflicts:

1. Abort the rebase instead of guessing.
2. Preserve both versions for inspection.
3. Reconcile product artifacts using their validation, completeness, state,
   reasons, warnings, and metrics.
4. Run the complete test suite and artifact validators.
5. Commit the reconciled result and retry publishing.

## GitHub Actions Behavior

The workflow retries normal non-fast-forward pushes after fetching and
rebasing. A rebase conflict fails loudly because unattended Git cannot safely
choose between conflicting generated artifacts.

When that happens, reconcile the artifacts rather than cancelling or
discarding the completed run by default.

## Cooperative Pause and Drain

GitHub Actions cannot pause and resume the same runner. The workflow therefore
uses repository variable `PIPELINE_MODE` with these values:

- `running`: keep submitting products.
- `draining`: finish active products, submit no replacements, and do not chain.
- `paused`: finish active products, submit no replacements, block future work.

Use the separate `Control Sentiment Pipeline` workflow to issue `pause`,
`drain`, `resume`, or `status`. It intentionally has no pipeline concurrency
lock, so controls take effect while the main workflow is active. Active product
classification is never interrupted, so pause latency can be as long as the
slowest currently active product.

The scheduler maintains only the configured number of active products and
checks the cached mode once before refilling available worker slots.

## Soft Time Budget

The runner also stops refilling worker slots after its cooperative soft
deadline. Active products finish before artifacts are committed and pushed.

Routine runs use repository variable `PIPELINE_MAX_MINUTES`, defaulting to 300
minutes. The main workflow's `max_minutes` input overrides that value for a
single run. Keep the soft deadline below GitHub's hard job timeout so active
products have time to finish and publishing can complete.

The runner reports `stop_reason` as `time_budget_reached`, `mode_paused`,
`mode_draining`, or `queue_exhausted`. It logs a warning when the deadline is
crossed while products remain active.
