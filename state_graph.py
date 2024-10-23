import json
from types import NoneType
from typing import Annotated, Union

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages

from afunc import AFunc
from call_graph import Code2FlowCallGraphCreator
from code_retriever import CodeRetriever
from llm import init_coverage_llm
from prompt import PromptGenerator

ENABLE_CODE_EXTRACT_TOOL = True


class ExtractCodeArgsSchema(BaseModel):
    module_name: Union[str, NoneType] = Field(description="The module containing the code to be extracted or None if unknown.")
    class_name: Union[str, NoneType] = Field(description="The class containing the method to be extracted or None if unknown or if the code to be extracted is a function.")
    method_or_function_name: str = Field(description="The name of the method (if class_name is given) or the function (if class_name is not given) to be extracted.")


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


class ToolNode:
    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    def __call__(self, inputs: dict):
        if messages := inputs.get("messages", []):
            message = messages[-1]
        else:
            raise ValueError("No message found in input")
        outputs = []
        for tool_call in message.tool_calls:
            tool_result = self.tools_by_name[tool_call["name"]].invoke(
                tool_call["args"]
            )
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        return {"messages": outputs}


class PathEvaluator(object):

    MAJORITY_VOTE_NUM = 3

    def __init__(self, llm, prompt_generator):
        self.__llm = llm
        self.__prompt_generator = prompt_generator

        self.__tools = self._create_tools()
        if ENABLE_CODE_EXTRACT_TOOL:
            self.__prompt_generator.tool_use_enabled = True
            self.__llm = llm.bind_tools(self.__tools)

        self.__afunc = None
        self.__paths = []
        self.__tests_to_run = []

    def __create_state_graph(self, path):
        graph_builder = StateGraph(State)

        graph_builder.add_node("chatbot", ChatbotNode(self.__llm))
        graph_builder.add_node("path_logic", PathLogicNode(self.__afunc, path, self.__prompt_generator))
        graph_builder.add_node("tools", ToolNode(tools=self.__tools))

        graph_builder.add_edge(START, "path_logic")

        # This conditional edge routes to the chatbot if more paths/functions can be explored. Otherwise, it routes to the end.
        graph_builder.add_conditional_edges(
            "path_logic",
            lambda state: "__end__" if state["stop_flag"] else "chatbot",
            {"chatbot": "chatbot", "__end__": "__end__"},
        )

        # This conditional edge routes to the tool node if a tool node was requested and to the main logic node otherwise.
        graph_builder.add_conditional_edges(
            "chatbot", self.route_tools,
            {"path_logic": "path_logic", "tools": "tools"},
        )

        graph_builder.add_edge("tools", "chatbot")

        return graph_builder.compile()

    @staticmethod
    def route_tools(state: State):
        """
        Use in the conditional_edge to route to the ToolNode if the last message has tool calls.
        Otherwise, route to the path logic node.
        """
        if not ENABLE_CODE_EXTRACT_TOOL:
            # tool functionality is disabled
            return "path_logic"
        if isinstance(state, list):
            ai_message = state[-1]
        elif messages := state.get("messages", []):
            ai_message = messages[-1]
        else:
            raise ValueError(f"No messages found in input state to tool_edge: {state}")
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return "path_logic"

    def _create_tools(self):
        input_format = {
            "module_name": {
                "type": "string",
                "description": "The module containing the code to be extracted or None if unknown.",
            },
            "class_name": {
                "type": "string",
                "description": "The class containing the method to be extracted or None if unknown or if the code to be extracted is a function.",
            },
            "method_or_function_name": {
                "type": "string",
                "description": "The name of the method (if class_name is given) or the function (if class_name is not given) to be extracted.",
            }
        }
        output_format = {
            "code": "string",
        }
        code_extract_tool = StructuredTool(name="extract_code",
                                           func=self.__prompt_generator.code_retriever.generate_code_extract_func(),
                                           description="The tool for extracting the source code of the given function or method.",
                                           args_schema=ExtractCodeArgsSchema,
                                           input_format=input_format,
                                           output_format=output_format)
        return [code_extract_tool]

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
