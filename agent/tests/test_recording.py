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
