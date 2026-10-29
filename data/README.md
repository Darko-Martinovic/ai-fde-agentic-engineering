# UnderCover seed data

The data behind UnderCover Travel Insurance, a fictional insurer. Everything here is invented, including the people, the airlines and the hotels. Amounts are in US dollars.

## The insurer's systems

- `company.json`: company settings, including the $1,000 payout approval limit, which seeding makes the first row of the platform's settings; from then on the limit is a setting a senior handler changes on the dashboard.
- `plans.json`: the three plans (Economy, Premium, First) with their limits, waiting periods and deductibles, and the three add-ons.
- `policies.json`: one policy per trip, with the plan, the add-ons, the purchase date, the trip and the travelers.
- `customers.json`: contact details and claim history, with the date and a one line summary of each earlier claim. This is personal data.
- `handlers.json`: the claims handlers, with the email each signs in with (`dana.whitfield@undercover.example` and so on, as users in the Supabase project's Auth). Dana Whitfield, the senior handler, can sign off payouts over the limit and so change the settings, start and stop rounds and review the improver's proposals; Marcus Oyelaran and Priya Raman can't (`can_approve_over_limit`).
- `claims.json`: the claims queue, twenty-five claims. Each has the customer's story, the items claimed and the supporting documents as text.

## The claim agent and its improvement

- `models.json`: the models the claim agent may use, on OpenRouter, each with its reasoning efforts, its prices in US dollars per million tokens and the options it's built with, and the model version 1 runs on (GPT-6 Luna at low reasoning effort). A student on free models sets `MODEL_NAME` in `.env`, as `provider:model`, before seeding: it's then the only model allowed, at no reasoning effort of its own and a price of 0, the improver runs on it too, and the judge isn't called.
- `improvement.json`: what a round of improvement works to, the lab's values: the objectives on the held-out set (accuracy 0.6, grade 1.0), the noise and the tolerance for each measure, the spending limit for each round ($0.50) and the claim agents at once in a round's evaluations (25). Seeding makes them, with the approval limit, the first row of the settings.

The claim agent's first instructions and the improver's are in `backend/instructions/`, beside the improver's first recipe, the lab's.

## The documents

- `policy_wording.md`: the contract with the customer. Short enough to fit in a prompt.
- `claims_manual.md`: the internal handling manual. Longer, and it holds rules the wording does not, such as the third claim in 12 months, losses to wild animals and meals without receipts.

## The evaluation set

- `evals/decisions.json`: the handlers' decisions on the twenty-five claims in the queue: approve, decline or refer, the payout, the calculation, the reason and what each claim tests. An agent deciding claims must never be shown this file.
- `evals/held_out_claims.json` and `evals/held_out_decisions.json`: twenty-five more claims with their decisions, kept out of the queue for checking that an improvement generalizes. They have the same blend as the queue. Keep them out of sight while you write a prompt or a rule, and score them afterwards.

The queue is the development set and the held-out claims are the test set. Nothing is trained on either.

Every decision also carries a few tags. `difficulty` is `routine`, `hard` (the wording settles it and it stretches a small model) or `manual` (it needs something the prompt does not hold, listed in `needs`: the claims manual, the customer's history or both). `failure_class` groups the hard claims that one rule should fix. `tone` is `plain`, `amusing` or `nod`. `tiny` marks a subset of five claims in each set, one of each kind, which fits inside a free model's daily allowance.

The labs define `get_sample_data(tiny=False, held_out=False)`, which returns the claims of either set with their decisions.

A decision is scored on two things: the decision itself and the payout. A valid claim that pays more than $1,000 is still an approve. The payment waits for a handler's sign-off, and `over_approval_limit` marks those claims.

## The security claim

- `security/`: CLM-1901, a stolen watch whose story carries an instruction to the AI to approve it in full, with its policy, its customer and the handler's decision (decline). It is a prompt injection kept for security testing, in a folder of its own. Seeding puts the claim in the queue with its policy and customer, and never its handler's decision, so it is in neither evaluation set; the agent's security check refers it.
