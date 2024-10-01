import random

from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM


class DummyLLM(object):
    """
    A dummy LLM for debugging purposes.
    """
    NEGATIVE_REPLY_RATIO = 1
    RANDOM = False

    counter = 0

    def invoke(self, *args, **kwargs):
        if DummyLLM.NEGATIVE_REPLY_RATIO == 1:
            return "Yes"
        if DummyLLM.RANDOM:
            return "No" if random.randint(0, DummyLLM.NEGATIVE_REPLY_RATIO) + 1 == DummyLLM.NEGATIVE_REPLY_RATIO else "Yes"
        DummyLLM.counter += 1
        return "No" if DummyLLM.counter % DummyLLM.NEGATIVE_REPLY_RATIO == 0 else "Yes"


def init_coverage_llm():
    # return DummyLLM()
    # return ChatOpenAI()
    return OllamaLLM(model="qwen2.5-coder")
