import random

from langchain_openai import ChatOpenAI

class DummyLLM(object):
    """
    A dummy LLM for debugging purposes.
    """
    NEGATIVE_REPLY_RATIO = 3
    RANDOM = False

    counter = 0

    def invoke(self, *args, **kwargs):
        if DummyLLM.RANDOM:
            return "No" if random.randint(0, DummyLLM.NEGATIVE_REPLY_RATIO) + 1 == DummyLLM.NEGATIVE_REPLY_RATIO else "Yes"
        DummyLLM.counter += 1
        return "No" if DummyLLM.counter % DummyLLM.NEGATIVE_REPLY_RATIO == 0 else "Yes"


def init_coverage_llm():
    return DummyLLM()
    # return ChatOpenAI()
