import ast
import os

from afunc import AFunc


class CodeRetriever(object):
    def __init__(self, root_code_dir=None, root_test_dir=None):
        self.__root_code_dir = root_code_dir
        self.__root_test_dir = root_test_dir

    @staticmethod
    def __find_module_path(root_dir, module_name):
        for dir_path, _, files in os.walk(root_dir):
            if f"{module_name}.py" in files:
                return os.path.join(dir_path, f"{module_name}.py")
        return None

    @staticmethod
    def __extract_source_code(node, lines):
        """Extract the source code of the node from the file's lines."""
        return ''.join(lines[node.lineno - 1:node.end_lineno])

    def __retrieve_code(self, function_name, class_name, module_name, root_dir):
        # Find the module path
        module_path = self.__find_module_path(root_dir, module_name)
        if module_path is None:
            raise ValueError(f"Module '{module_name}' not found in '{root_dir}'.")

        # Read the source code of the module
        with open(module_path, 'r') as f:
            source_lines = f.readlines()

        # Parse the module's AST
        with open(module_path, 'r') as f:
            module_ast = ast.parse(f.read())

        # Traverse the AST to find the class and function
        for node in ast.walk(module_ast):
            if isinstance(node, ast.ClassDef) and class_name is not None and node.name == class_name:
                # If class is specified, find the function within the class
                for class_node in node.body:
                    if isinstance(class_node, ast.FunctionDef) and class_node.name == function_name:
                        return self.__extract_source_code(class_node, source_lines)
            elif isinstance(node, ast.FunctionDef) and class_name is None and node.name == function_name:
                # If no class is specified, find the standalone function
                return self.__extract_source_code(node, source_lines)

        raise ValueError(f"Function or method '{function_name}' not found in module '{module_name}'.")

    def retrieve_source(self, afunc):
        return self.__retrieve_code(afunc.function_name, afunc.class_name, afunc.module_name, self.__root_code_dir)

    def retrieve_test(self, afunc):
        return self.__retrieve_code(afunc.function_name, afunc.class_name, afunc.module_name, self.__root_test_dir)

    def retrieve(self, afunc):
        if afunc.is_test_function():
            return self.retrieve_test(afunc)
        return self.retrieve_source(afunc)


if __name__ == "__main__":
    code_retriever = CodeRetriever(r"C:\Users\ilyak\PycharmProjects\ansible\lib",
                                   r"C:\Users\ilyak\PycharmProjects\ansible\test\units")
    test_afunc = AFunc(node_name="test_action::TestActionBase.test_action_base__execute_remote_stat")
    code = code_retriever.retrieve(test_afunc)
    print(code)
