import pytest

from agent import config


def test_the_default_model_is_gpt_6_luna_at_low_reasoning():
    default = config.current_model()
    assert default.spec == "openrouter:openai/gpt-6-luna"
    assert default.label == "GPT-6 Luna"
    assert default.options == {"reasoning_effort": "low"}


def test_model_name_chooses_the_model(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "ollama:qwen3.5:9b")
    chosen = config.current_model()
    assert (chosen.provider, chosen.name) == ("ollama", "qwen3.5:9b")


def test_another_model_runs_with_its_own_options():
    haiku = config.model("anthropic:claude-haiku-5-5")
    assert haiku.options == {"reasoning_effort": "low", "max_tokens": 16000}
    assert config.model("openrouter:openrouter/free").options == {}


def test_a_model_not_allowed_is_refused():
    with pytest.raises(ValueError, match="not one of the models"):
        config.model("openrouter:someone/unknown")


def test_every_model_has_a_price_and_a_known_provider():
    for allowed in config.models().values():
        assert allowed.provider in {"openrouter", "anthropic", "ollama"}
        assert allowed.input_price >= 0
        assert allowed.output_price >= 0
