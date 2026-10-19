from langchain_core.language_models.fake_chat_models import GenericFakeChatModel


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self
