from fastapi import FastAPI
from langchain_core.runnables import chain
from langserve import add_routes
import uvicorn

from afunc import AFunc
from call_graph import Code2FlowCallGraphCreator
from code_retriever import CodeRetriever
from llm import init_coverage_llm
from prompt import PromptGenerator
from state_graph import PathEvaluator

from pydantic import BaseModel


class GraphExecutionParams(BaseModel):
    root_code_dir: str
    root_test_dir: str
    function_name: str
    class_name: str
    module_name: str
    dot_file_path: str

@chain
def execute_graph(params: GraphExecutionParams):
    try:
        target_function = AFunc(function_name=params["function_name"], class_name=params.get("class_name"),
                                module_name=params["module_name"])
        paths = Code2FlowCallGraphCreator(dot_file_path=params["dot_file_path"]).find_all_test_paths(target_function)
        llm = init_coverage_llm()
        prompt_generator = PromptGenerator(CodeRetriever(root_code_dir=params["root_code_dir"], root_test_dir=params["root_test_dir"]))
        tests_to_run = PathEvaluator(llm, prompt_generator).evaluate_paths(target_function, paths)

        return "\n".join([str(t) for t in tests_to_run])
    except Exception as e:
        return f"Graph execution failed: {str(e)}"

def main():
    app = FastAPI(title="LangChain Server", version="1.0", description="A simple API server demonstrating LLM-based coverage")
    add_routes(app, execute_graph, path="/chain")
    uvicorn.run(app, host="localhost", port=8000)


if __name__ == "__main__":
    main()
