def test_list_models(client):
    models = client.get("/api/models").json()
    haiku = {"spec": "anthropic:claude-haiku-5-5", "label": "Claude Haiku 5.5"}
    assert haiku | {"default": False} in models
    assert [m["spec"] for m in models if m["default"]] == [
        "openrouter:openai/gpt-6-luna"
    ]
