import pytest
from langchain_core.messages import AIMessage

from agent import recording


def test_steps_from_a_reply():
    thinking = AIMessage(
        content="Reading the claim.",
        tool_calls=[{"name": "get_policy", "args": {"policy_id": "P"}, "id": "1"}],
    )
    assert recording.steps(thinking) == [
        ("reply", "Reading the claim."),
        ("tool_call", 'get_policy {"policy_id": "P"}'),
    ]


def reply(token_usage):
    message = AIMessage(content="", response_metadata={"token_usage": token_usage})
    message.usage_metadata = {
        "input_tokens": 20000,
        "output_tokens": 1000,
        "total_tokens": 21000,
    }
    return message


def test_the_cost_openrouter_reports_is_the_cost():
    assert recording.cost(reply({"cost": 0.0042})) == 0.0042


@pytest.mark.parametrize("token_usage", [{}, None, {"cost": None}])
def test_a_local_model_reports_no_cost_and_costs_nothing(token_usage):
    assert recording.cost(reply(token_usage)) == 0


def test_a_reply_with_no_usage_has_no_tokens():
    assert recording.tokens(AIMessage(content="")) == (0, 0)
    assert recording.tokens(None) == (0, 0)
