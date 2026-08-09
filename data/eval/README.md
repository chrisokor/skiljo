# Eval Dataset

Split: 30 train / 15 dev / 15 test (60 examples total), expanded from the week 2
baseline of 20 train examples per plan #51 (see `docs/POLICY_CORPUS.md`).

- `train/` — used for prompt tuning and iteration. Never off limits.
- `dev/` — validation set during development. Never tune against this.
- `test/` — held-out set, CI-only, `.CODEOWNERS`-gated. **Never manually
  inspect or tune against this set** (see CLAUDE.md system invariant 5).

Each example is a pair of files sharing a numeric prefix and slug:

- `NN_slug.policy.txt` — source policy text (paraphrased from the public
  policy named in `docs/POLICY_CORPUS.md`)
- `NN_slug.skill.yaml` — hand-labeled ground-truth `Skill` spec
  (`schemas/skill.schema.json`) extracted from that text

## Corpus allocation

The corpus documents in `docs/POLICY_CORPUS.md` yield multiple distinct rule
clusters each; each cluster is labeled as an independent example so that a
single source document can appear in more than one split without leaking the
*same* rule cluster across splits.

Per the corpus doc's hold-out discipline, the following documents are
reserved for `test/` wherever a **new** rule cluster is introduced (rather
than a cluster already labeled in `train/` during week 2): Steam refund
policy (#14), Shopify subscription policy (#12, the intra-document
no-refund-vs-case-by-case contradiction), Cloudflare Business SLA + Billing
Policy (#16), and DigitalOcean Droplets SLA family (#17). Cloudflare and
DigitalOcean do not appear in `train/` or `dev/` at all.

## Loading

`packages/core/tests/test_eval_data.py` validates every example: the skill
YAML parses and validates against the `Skill` pydantic model, and its paired
policy text file exists and is non-empty.
