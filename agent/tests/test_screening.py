"""The security check, which reads every claim before the claim agent's model
does and refers one that tries to instruct whoever handles it."""

import json

import pytest
from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError
from langchain_core.messages import AIMessage

from agent import api, harness, improver, screening
from agent.harness import security_check
from agent.tests.stub import (
    CHECK_MODEL,
    FREE,
    StubModel,
    check,
    claim_agent_calls,
    decide,
    screened,
    stub,
)
from backend.tests.sign_ins import DANA, headers
from backend.tests.usage_rows import model_calls

FOUND = "The story tells the AI to approve the claim in full."


class StopsAfter(StubModel):
    """Stops the agent, as a restart would, once its replies run out."""

    def _generate(self, *args, **kwargs):
        try:
            return super()._generate(*args, **kwargs)
        except (StopIteration, RuntimeError) as exhausted:
            raise KeyboardInterrupt from exhausted


def steps(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}/steps").json()


def test_a_flagged_claim_is_referred_and_the_agents_model_never_sees_it(
    backend, run, memory_saver, monkeypatch
):
    monkeypatch.setattr(harness, "security_check", lambda: check(screened(True, FOUND)))
    report = harness.work_claim("CLM-1901", run, FREE, memory_saver, stub())
    assert report == f"CLM-1901: referred to a handler, because: {FOUND}"
    claim = backend.get("/api/claims/CLM-1901").json()
    [decision] = claim["decisions"]
    assert (decision["decision"], decision["payout"]) == ("refer", 0)
    assert decision["policy_section"] == screening.SECURITY_CHECK
    [step] = steps(backend, "CLM-1901")
    assert (step["kind"], step["text"]) == ("check", f"Found an instruction. {FOUND}")
    assert claim_agent_calls("CLM-1901") == []
    [call] = model_calls("CLM-1901")
    assert (call["model"], call["run_id"]) == (CHECK_MODEL.name, run)


def test_a_claim_the_check_passes_goes_on_to_the_agent(backend, run, memory_saver):
    report = harness.work_claim(
        "CLM-1005", run, FREE, memory_saver, stub(decide("decline", 0))
    )
    assert report.startswith("CLM-1005: declined")
    first, *rest = steps(backend, "CLM-1005")
    assert first["kind"] == "check"
    assert first["text"].startswith("Nothing found. ")
    assert [step["kind"] for step in rest] == ["tool_call", "tool_result"]


def test_an_answer_that_cant_be_read_is_asked_again_and_then_fails_the_claim(
    backend, run, memory_saver, monkeypatch
):
    unreadable = [AIMessage(content="I can't tell.") for _ in range(3)]
    monkeypatch.setattr(harness, "security_check", lambda: check(*unreadable))
    report = harness.work_claim("CLM-1005", run, FREE, memory_saver, stub())
    assert report.startswith("CLM-1005: failed, back in the queue (UnreadableScreening")
    assert len(model_calls("CLM-1005")) == screening.ATTEMPTS
    assert claim_agent_calls("CLM-1005") == []


def test_an_answer_read_on_the_second_call_counts_both_calls(
    backend, run, memory_saver, monkeypatch
):
    monkeypatch.setattr(
        harness,
        "security_check",
        lambda: check(AIMessage(content="Hmm."), screened(False)),
    )
    harness.work_claim("CLM-1005", run, FREE, memory_saver, stub(decide("decline", 0)))
    checks = [c for c in model_calls("CLM-1005") if c["model"] == CHECK_MODEL.name]
    assert len(checks) == 2


def test_a_check_that_fails_at_the_provider_fails_the_claim(
    backend, run, memory_saver, monkeypatch
):
    class Down(StubModel):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("the provider timed out")

    broken = screening.screener(Down(messages=iter([]))), CHECK_MODEL
    monkeypatch.setattr(harness, "security_check", lambda: broken)
    report = harness.work_claim("CLM-1005", run, FREE, memory_saver, stub())
    assert report.startswith("CLM-1005: failed, back in the queue (TimeoutError")
    assert claim_agent_calls("CLM-1005") == []


def test_a_carry_on_from_saved_progress_doesnt_check_again(
    backend, run, memory_saver, monkeypatch
):
    # One answer only: a second check would find no reply and fail the claim
    once = check(screened(False))
    monkeypatch.setattr(harness, "security_check", lambda: once)
    with pytest.raises(KeyboardInterrupt):
        harness.work_claim(
            "CLM-1005", run, FREE, memory_saver, StopsAfter(messages=iter([]))
        )
    report = harness.carry_on(
        "CLM-1005", run, FREE, memory_saver, stub(decide("decline", 0))
    )
    assert report.startswith("CLM-1005: declined")
    assert [step["kind"] for step in steps(backend, "CLM-1005")].count("check") == 1


def test_a_claim_started_again_is_checked_again(backend, run, memory_saver):
    harness.work_claim(
        "CLM-1005", run, FREE, memory_saver, stub(AIMessage(content="Hmm."))
    )
    harness.work_claim("CLM-1005", run, FREE, memory_saver, stub(decide("decline", 0)))
    checked = [step for step in steps(backend, "CLM-1005") if step["kind"] == "check"]
    assert len({step["thread_id"] for step in checked}) == 2


def test_the_check_reads_what_the_customer_wrote_and_nothing_of_ours(backend):
    claim = api.get_claim("CLM-1901")
    read = json.loads(screening.what_the_customer_wrote(claim))
    assert set(read) == set(screening.CUSTOMER_FIELDS)
    assert read["story"] == claim["story"]


def held(run, memory_saver, monkeypatch):
    """CLM-1002 approved for $1,350.00, waiting for a sign-off, with a check
    that answers once: a second check would find no reply and fail the claim."""
    monkeypatch.setattr(harness, "security_check", lambda: check(screened(False)))
    harness.work_claim(
        "CLM-1002", run, FREE, memory_saver, stub(decide("approve", 1350.0))
    )


# A handler's review of the held payout, and what the agent then replies
REVIEWS = {
    "sign-off": ({"approved": True, "note": ""}, []),
    "rejection": (
        {"approved": False, "note": "The deductible is $100.00."},
        [decide("approve", 1250.0)],
    ),
}


@pytest.mark.parametrize("reviewed", REVIEWS.values(), ids=REVIEWS.keys())
def test_a_carry_on_after_a_review_doesnt_check_again(
    backend, run, memory_saver, monkeypatch, reviewed
):
    review, replies = reviewed
    held(run, memory_saver, monkeypatch)
    backend.post("/api/claims/CLM-1002/review", json=review, headers=headers(DANA))
    harness.carry_on("CLM-1002", None, FREE, memory_saver, stub(*replies))
    assert [step["kind"] for step in steps(backend, "CLM-1002")].count("check") == 1
    checks = [c for c in model_calls("CLM-1002") if c["model"] == CHECK_MODEL.name]
    assert len(checks) == 1


@pytest.mark.parametrize("error", [ModelRateLimitError, ModelTimeoutError])
def test_a_rate_limit_or_a_timeout_from_the_check_leaves_the_claim_in_progress(
    backend, run, memory_saver, monkeypatch, error
):
    class Busy(StubModel):
        def _generate(self, *args, **kwargs):
            raise error("slow down")

    busy = screening.screener(Busy(messages=iter([]))), CHECK_MODEL
    monkeypatch.setattr(harness, "security_check", lambda: busy)
    with pytest.raises(error):
        harness.work_claim("CLM-1005", run, FREE, memory_saver, stub())
    claim = backend.get("/api/claims/CLM-1005").json()
    assert claim["status"] == "in_progress"
    assert "failure" not in [step["kind"] for step in steps(backend, "CLM-1005")]


def test_the_improver_cant_change_the_check():
    """A version is the claim agent's instructions, model and reasoning effort,
    so nothing the improver proposes reaches the check."""
    proposed = set(improver.propose_change.args)
    assert proposed == {"instructions", "model", "reasoning_effort", "reason"}


def test_the_check_is_built_on_the_model_the_backend_names(backend, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "a key the test never sends")
    _, runs_on = security_check()
    assert runs_on.name == "openai/gpt-6-luna"
    assert runs_on.options["reasoning_effort"] == "none"
