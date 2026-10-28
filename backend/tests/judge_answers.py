"""The judge as the tests stand in for it: Jev's answer as the Decisions
endpoint sends it, and the grade it gives, which the root conftest.py gives
every claim in place of the judge's call, so no test reaches OpenRouter."""

from backend import judge
from backend.run_models import Grade

# Jev's answer: B most likely, scored 2.2, the checks at 0.8 and 0.3
ANSWER = {
    "answers": {
        "grade": {
            "type": "score",
            "score": 2.2,
            "probabilities": {"0": 0.05, "1": 0.1, "2": 0.45, "3": 0.4},
        },
        "same_grounds": {"type": "noul", "noul": 0.8},
        "same_section": {"type": "noul", "noul": 0.3},
    },
    "model": "jev",
    "usage": {"input_tokens": 400, "output_tokens": 3, "cost": 0.00002},
}
B = Grade(grade=2.2, letter="B", same_grounds=0.8, same_section=0.3, judge_cost=0.00002)

# The judge's own call, before the tests' stand-in takes its place
REAL_ASK = judge.ask
