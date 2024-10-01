from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages

from afunc import AFunc
from call_graph import Code2FlowCallGraphCreator
from code_retriever import CodeRetriever
from llm import init_coverage_llm
from prompt import PromptGenerator


class State(TypedDict):
    messages: Annotated[list, add_messages]
    result_flag: bool
    stop_flag: bool


class ChatbotNode:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: State):
        return {"messages": [self.llm.invoke(state["messages"])], "result_flag": False, "stop_flag": False}


class PathLogicNode:
    def __init__(self, afunc, path, prompt_generator):
        self.afunc = afunc
        self.path = path
        self.prompt_generator = prompt_generator
        self.current_step = 0

    def __call__(self, inputs):
        messages = inputs["messages"]
        if len(messages) == 0:
            # this is the very first call, just create the initial prompt and exit
            output = self.prompt_generator.create_initial_prompt(self.path, self.current_step)
            return {"messages": [("user", output)], "result_flag": False, "stop_flag": False}

        # Analyze the reply - there are three cases:
        # 1) The current step answer is 'Yes' and there are more steps to be taken;
        # 2) The current step answer is 'Yes' and this is the last step;
        # 3) The current step answer is 'No'.
        reply = messages[-1]
        yes_or_no = self.prompt_generator.analyze_llm_reply(reply)
        if yes_or_no == 'n':
            return {"messages": [], "result_flag": False, "stop_flag": True}
        elif yes_or_no == 'y':
            self.current_step += 1
            if self.current_step == len(self.path) - 1:
                return {"messages": [], "result_flag": True, "stop_flag": True}
        else:
            raise ValueError(f"Unexpected reply from LLM: {reply}")

        output = self.prompt_generator.create_prompt(self.path, self.current_step)

        return {"messages": [("user", output)], "result_flag": False, "stop_flag": False}


class PathEvaluator(object):

    MAJORITY_VOTE_NUM = 3

    def __init__(self, llm, prompt_generator):
        self.__llm = llm
        self.__prompt_generator = prompt_generator

        self.__afunc = None
        self.__paths = []
        self.__tests_to_run = []

    def __create_state_graph(self, path):
        graph_builder = StateGraph(State)

        graph_builder.add_node("chatbot", ChatbotNode(self.__llm))
        graph_builder.add_node("path_logic", PathLogicNode(self.__afunc, path, self.__prompt_generator))

        graph_builder.add_edge(START, "path_logic")
        graph_builder.add_edge("chatbot", "path_logic")

        # This conditional edge routes to the chatbot if more paths/functions can be explored. Otherwise, it routes to the end.
        graph_builder.add_conditional_edges(
            "path_logic",
            lambda state: "__end__" if state["stop_flag"] else "chatbot",
            {"chatbot": "chatbot", "__end__": "__end__"},
        )

        return graph_builder.compile()

    def __run_single_state_graph(self, path):
        state_graph = self.__create_state_graph(path)
        initial_state = {"messages": [], "result_flag": False, "stop_flag": False}
        result = state_graph.invoke(initial_state)
        return result["result_flag"]

    def __evaluate_next_path(self):
        current_path = self.__paths.pop(0)
        current_test = current_path[0]
        if current_test in self.__tests_to_run:
            # already added - no need to evaluate this path
            return

        positive_replies_num = 0
        negative_replies_num = 0
        for _ in range(self.MAJORITY_VOTE_NUM):
            current_result = self.__run_single_state_graph(current_path)
            if current_result:
                positive_replies_num += 1
            else:
                negative_replies_num += 1
        if positive_replies_num > negative_replies_num:
            self.__tests_to_run.append(current_test)

    def evaluate_paths(self, afunc, paths):
        if len(paths) == 0:
            raise Exception("No valid paths to target function were found, no work to be done.")

        self.__afunc = afunc
        self.__paths = paths
        self.__tests_to_run = []

        while len(paths) > 0:
            self.__evaluate_next_path()

        return self.__tests_to_run


if __name__ == "__main__":
    target_function = AFunc(function_name="ensure_type", class_name=None, module_name="manager")
    test_paths = Code2FlowCallGraphCreator(dot_file_path=r"C:\Users\ilyak\PycharmProjects\callgraph.dot").find_all_test_paths(target_function)
    test_llm = init_coverage_llm()
    pg = PromptGenerator(CodeRetriever(root_code_dir=r"C:\Users\ilyak\PycharmProjects\ansible\lib\ansible\config",
                                       root_test_dir=r"C:\Users\ilyak\PycharmProjects\ansible\test\units\config"))
    tests_to_run = PathEvaluator(test_llm, pg).evaluate_paths(target_function, test_paths)
    print(*tests_to_run, sep='\n')
