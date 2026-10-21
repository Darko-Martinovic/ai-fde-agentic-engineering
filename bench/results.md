# Model comparison

Each run reseeds the database and works the claims through the harness, one
claim agent per claim, then reads each claim's decision and payout and the run's
usage through the API. A decision is right when it matches the handlers' in
`data/evals/decisions.json`; a payout is right when the decision is right and,
for an approval, the payout is within a dollar of theirs. A claim left
undecided counts as wrong. Model calls, tokens, cost and time are per claim;
the cost is at the prices in `models.toml`, and the local models cost nothing.
Percentages are the mean of the runs, with their range when they differ. A run
in which the provider answered no model call at all, as when a free model is
rate-limited, says nothing about the model: it isn't scored, it is listed under
"Runs refused", and the next `uv run -m bench` tries it again. A run the
provider stopped partway is scored, its unanswered claims counted as wrong.

![Accuracy by model](results.svg)

| Model | Claims | Runs | Decision right | Payout right | Undecided | Model calls | Tokens in / out | Cost | Time |
|---|---|---|---|---|---|---|---|---|---|
| Claude Haiku 5.5 | all (25) | 3 | 84% | 80% (76–84) | 1 | 6.6 | 37,043 / 1,923 | $0.0047 | 16 s |
| Claude Opus 5.5 | tiny (5) | 3 | 93% (80–100) | 93% (80–100) | 1 | 4.9 | 22,071 / 1,296 | $0.1142 | 21 s |
| Qwen 3.5 4B (local) | all (25) | 2 | 54% (52–56) | 46% (44–48) | 10 | 7.6 | 23,927 / 2,315 | $0.0000 | 65 s |

## The claims each model got wrong

### Claude Haiku 5.5, all claims

- CLM-1002 (1 of 3): handlers approve $580.00, agent refer $0.00
- CLM-1004 (2 of 3): handlers approve $186.00, agent approve $74.00
- CLM-1007 (1 of 3): handlers approve $50.00, agent waiting $0.00
- CLM-1011 (1 of 3): handlers approve $1,150.00, agent approve $1,330.00
- CLM-1019 (1 of 3): handlers refer $0.00, agent approve $210.00
- CLM-1023 (3 of 3): handlers refer $0.00, agent approve $61.00
- CLM-1024 (3 of 3): handlers refer $0.00, agent decline $0.00
- CLM-1025 (3 of 3): handlers refer $0.00, agent approve $71.00

### Claude Opus 5.5, tiny claims

- CLM-1007 (1 of 3): handlers approve $50.00, agent waiting $0.00

### Qwen 3.5 4B (local), all claims

- CLM-1002 (2 of 2): handlers approve $580.00, agent waiting $0.00
- CLM-1004 (2 of 2): handlers approve $186.00, agent waiting $0.00
- CLM-1007 (1 of 2): handlers approve $50.00, agent decline $0.00
- CLM-1009 (2 of 2): handlers approve $930.00, agent waiting $0.00
- CLM-1010 (1 of 2): handlers decline $0.00, agent approve $1,300.00
- CLM-1011 (2 of 2): handlers approve $1,150.00, agent approve $1,490.00
- CLM-1012 (1 of 2): handlers decline $0.00, agent approve $520.00
- CLM-1014 (2 of 2): handlers approve $605.00, agent waiting $0.00
- CLM-1015 (1 of 2): handlers decline $0.00, agent waiting $0.00
- CLM-1016 (1 of 2): handlers decline $0.00, agent approve $6,100.00
- CLM-1018 (2 of 2): handlers refer $0.00, agent approve $330.00
- CLM-1019 (2 of 2): handlers refer $0.00, agent approve $210.00
- CLM-1020 (1 of 2): handlers approve $240.00, agent decline $0.00
- CLM-1021 (2 of 2): handlers approve $825.00, agent approve $1,103.00
- CLM-1023 (2 of 2): handlers refer $0.00, agent waiting $0.00
- CLM-1024 (1 of 2): handlers refer $0.00, agent approve $300.00
- CLM-1025 (2 of 2): handlers refer $0.00, agent waiting $0.00

## Runs refused

- Gemma 4 31B (free), tiny claims: 1 of 1 runs refused
