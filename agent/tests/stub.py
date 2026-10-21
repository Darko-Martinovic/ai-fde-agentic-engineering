from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from agent.config import model

# A model to work claims on in tests, which never call it
FREE = model("openrouter:openrouter/free")


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self
