import pytest

from agent import config


def test_the_default_model_is_one_allowed():
    assert config.current_model().spec == "openrouter:deepseek/deepseek-v4.1-flash"
    assert config.current_model().label == "DeepSeek V4.1 Flash"


def test_model_name_chooses_the_model(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "ollama:qwen3.5:9b")
    chosen = config.current_model()
    assert (chosen.provider, chosen.name) == ("ollama", "qwen3.5:9b")


def test_a_model_not_allowed_is_refused():
    with pytest.raises(ValueError, match="not one of the models"):
        config.model("openrouter:someone/unknown")


def test_every_model_has_a_price_and_a_known_provider():
    for allowed in config.models().values():
        assert allowed.provider in {"openrouter", "anthropic", "ollama"}
        assert allowed.input_price >= 0
        assert allowed.output_price >= 0
