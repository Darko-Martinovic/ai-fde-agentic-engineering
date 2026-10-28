# The claims pilot

From the head of claims operations at UnderCover Travel Insurance.

## How claims work today

UnderCover sells travel insurance on three plans: Economy, Premium and First. Our three claims handlers work through a queue of claims by hand. For each claim, a handler reads the customer's story and documents and checks them against the policy and our policy wording. Then they approve the claim with a payout, decline it or refer it. A claim is referred when it needs someone's judgment or more information, as the claims manual explains.

## The pilot

We want an AI agent, the UnderCover Agent, to work the queue the way a handler does. For each claim it should:

- read the claim, the customer's policy and claim history, and the sections of the policy wording and the claims manual it needs
- approve, decline or refer the claim
- work out the payout when it approves
- explain the decision in two or three sentences, along with the relevant section of the policy

Our goal is to handle claims straight through, as accurately as our handlers do.

## Working the queue on its own

The agent works the queue in dispatches, with many claim agents at once:

- A dispatch works every claim left in progress and every waiting claim, oldest submitted first, with up to N claim agents working at once, from 1 to 25. Code chooses the claims and keeps track of the dispatch, with no model; when it finishes, its summary is built from our records. The agent can also work one named claim.
- Each claim goes to a claim agent that works that one claim on its own thread and reports back in a line: the decision and payout, with the reasons for a decline or a referral, or what went wrong. Every step on a claim is recorded on that claim.
- For each claim the agent looks up the sections of the policy wording and the claims manual it needs, the way a handler would, rather than being handed whole documents.
- Problems are put right automatically. A claim that hits a rate limit or a timeout waits and carries on from where it got to, as the same attempt, and one still hitting them after its waits stays in progress for the next dispatch. A claim that fails with any other error goes back to the queue and the same dispatch tries it once more, and a claim that fails twice is left for a handler. One bad claim never stops the dispatch, and no claim is ever decided or paid twice, even when a step runs again after a restart.
- When the agent approves a payout over the approval limit ($1,000 to begin with), it stops and waits for a handler, keeping everything it has worked out. The handler signs the payout off, and the agent picks the claim up straight away and pays it, recording who signed off and when; between the sign-off and the payment the claim shows as in progress. Or the handler rejects the payout with a note that says what's wrong: the agent looks at the claim again in its light and decides again, and that decision always goes back to a handler. A payout rejected twice is referred to a handler. If the agent isn't running at the time, the next dispatch picks the claim up.
- Work survives a restart. If the agent is stopped partway through a claim, by a crash or a restart, the claim stays in progress and the next dispatch carries it on from where it got to, which doesn't count as a new attempt. Stop on the dashboard starts no more claims, lets those working finish, and shows the dispatch as stopped.
- The tokens and the cost of every model call, and the time the agent spends working on each claim, leaving out any wait for a handler, are recorded with the dispatch or evaluation they happened in.
- Evaluations check the agent's work against our handlers' decisions: an evaluation works its own copies of a labelled set's claims, the queue's 25 or the held-out ones, all of them or their five `tiny` ones, through the same dispatcher and claim agent. The copies never show in the queue, a dispatch never carries them on, and nobody can sign them off or decide them.

## Improving the agent

A second agent, the improver, improves the claim agent in rounds, as our team's experiment in `labs/week2day5.ipynb` did, and a handler stays in charge of every change:

- The claim agent works from a configuration: its instructions, its model and its reasoning effort. Every change makes a new version, kept with why, who proposed it and who approved it. Dispatches and evaluations use the current version; version 1 is GPT-6 Luna at low reasoning effort.
- A senior handler starts a round. The current version is evaluated where it needs to be, once on the evaluation set and twice on the held-out set. Then the improver follows its recipe: it reads the results, proposes a change, and waits. A senior handler approves the change, after a confirmation, or rejects it with a reason the improver reads.
- An approved change is evaluated the same way, and the business's rule keeps it or rolls it back from its held-out scores beside the current version's: it must meet the objectives, improve at least one score by more than the noise, and make none worse by more than the tolerance.
- The improver then proposes a better recipe for the next round, which a handler approves or rejects the same way.
- A judge grades each of the agent's explanations against the handler's reason, so a round can tell a better decision from a better explanation.
- A round spends no more than its spending limit on the improver, the claim agents and the judge, and refuses evaluations it can't afford. A handler can stop a round; a version not yet judged is rolled back.
- The improver reads the evaluation set's mistakes beside our handlers' decisions, reasons and references, which the claim agent never sees. Of the held-out set it sees only the scores, so the held-out claims can tell us whether a change helps on claims nobody tuned it for.

## Signing in

Handlers sign in to the dashboard with their email. Anyone signed in sees everything. Only a handler who can sign off payouts over the approval limit (Dana Whitfield) signs off or rejects a held payout, decides a claim over the limit, changes the settings, starts or stops a round, and approves or rejects the improver's proposals; the others see why they can't.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off, decided or left for a handler.
- A way to start a dispatch from the queue page, choosing N, and to stop it.
- The dispatch as it happens: each of its claims and where it stands, its model cost and its time, and, when it finishes, a summary built from our records: how many claims were approved, declined and referred, each payout waiting for a sign-off, and each claim left for a handler or still in progress.
- A Scoreboard that starts evaluations and lists them, newest first, with how often the agent agrees with our handlers, what its mistakes cost, how many claims go straight through, and what a claim costs and takes; each evaluation opens to its claims, the agent's decision beside the handler's.
- Each claim in full, with the agent's decision and its reasons.
- What the agent is doing on a claim while it works, step by step, including the sections it read and any attempt that failed.
- The claim agent's configuration: every version, what it changed from the one before as a diff, its model and reasoning effort, its held-out scores, and the verdict on it.
- The settings, with who changed them last: the approval limit, and what a round works to (the objectives, the noise, the tolerance, the spending limit and the claim agents at once), changed only after a confirmation.
- The Improvement page: where a round has got to as it happens, the proposal waiting with what it would change, the rounds so far with their held-out scores before and after, the verdict and why, who approved or rejected what and when, and what each cost, a chart of the versions tried, and the recipe's versions.

## Rules

- A payout over the approval limit needs a senior handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay. The limit is a setting, $1,000 to begin with, and each decision keeps the limit it was held under.
- Decisions follow the policy wording and the claims manual. The wording comes first, and the manual says how to read it.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work. The claim agent must never see them; the improver sees those on the evaluation set, never the held-out set's.
- Nothing the improver proposes takes effect until a senior handler approves it.
- Amounts are in US dollars.

## Our records

Everything is in `data/`, described in `data/README.md`: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No roles beyond the approval limit. Everyone signed in sees everything.
- No real payments.
- No messages to customers.