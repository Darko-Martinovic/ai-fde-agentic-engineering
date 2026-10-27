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
- When the agent approves a payout over $1,000, it stops and waits for a handler, keeping everything it has worked out. The handler signs the payout off, and the agent picks the claim up straight away and pays it, recording who signed off and when; between the sign-off and the payment the claim shows as in progress. Or the handler rejects the payout with a note that says what's wrong: the agent looks at the claim again in its light and decides again, and that decision always goes back to a handler. A payout rejected twice is referred to a handler. If the agent isn't running at the time, the next dispatch picks the claim up.
- Work survives a restart. If the agent is stopped partway through a claim, by a crash or a restart, the claim stays in progress and the next dispatch carries it on from where it got to, which doesn't count as a new attempt. Stop on the dashboard starts no more claims, lets those working finish, and shows the dispatch as stopped.
- The tokens and the cost of every model call, and the time the agent spends working on each claim, leaving out any wait for a handler, are recorded with the dispatch or evaluation they happened in.
- Evaluations check the agent's work against our handlers' decisions: an evaluation works its own copies of a labelled set's claims, the queue's 25 or the held-out ones, all of them or their five `tiny` ones, through the same dispatcher and claim agent. The copies never show in the queue, a dispatch never carries them on, and nobody can sign them off or decide them.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off, decided or left for a handler.
- A way to start a dispatch from the queue page, choosing N and the model, and to stop it.
- The dispatch as it happens: each of its claims and where it stands, its model cost and its time, and, when it finishes, a summary built from our records: how many claims were approved, declined and referred, each payout waiting for a sign-off, and each claim left for a handler or still in progress.
- A Scoreboard that starts evaluations and lists them, newest first, with how often the agent agrees with our handlers, what its mistakes cost, how many claims go straight through, and what a claim costs and takes; each evaluation opens to its claims, the agent's decision beside the handler's.
- Each claim in full, with the agent's decision and its reasons.
- What the agent is doing on a claim while it works, step by step, including the sections it read and any attempt that failed.
- The claim agent's instructions, read only.

## Rules

- A payout over $1,000 needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording and the claims manual. The wording comes first, and the manual says how to read it.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work. The agent must never see them.
- Amounts are in US dollars.

## Our records

Everything is in `data/`, described in `data/README.md`: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real payments.
- No messages to customers.