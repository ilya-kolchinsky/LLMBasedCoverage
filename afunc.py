class AFunc(object):
    """
    AFunc stands for "analyzed function" and represents a function or method in a project.
    """
    def __init__(self, function_name=None, class_name=None, module_name=None, node_name=None):
        if node_name is not None:
            self.node_name = node_name
            self.module_name, self.class_name, self.function_name = self.__node_name_to_function(node_name)
        else:
            self.module_name = module_name
            self.class_name = class_name
            self.function_name = function_name
            self.node_name = self.__function_to_node_name(self.module_name, self.class_name, self.function_name)

    def __repr__(self):
        return self.node_name

    def __str__(self):
        return self.node_name

    def __eq__(self, other):
        return isinstance(other, AFunc) and self.node_name == other.node_name

    def is_test_function(self):
        return self.function_name.startswith(self.get_test_method_prefix())

    @staticmethod
    def __function_to_node_name(module_name, class_name, function_or_method_name):
        return f"{module_name}::{class_name}.{function_or_method_name}" \
               if class_name is not None and class_name != 'None' \
               else f"{module_name}::{function_or_method_name}"

    @staticmethod
    def __node_name_to_function(node_name):
        """
        Converts a node name in the format:
        - 'ModuleName::ClassName.method_name' (method in a class)
        - 'ModuleName::FunctionName' (standalone function)
        Returns a tuple (module_name, class_name, method_name), where class_name or method_name
        may be None if the node represents a standalone function.
        """
        if '.' in node_name:
            # This is a method in a class, so we split by '.' first
            module_class_part, method_name = node_name.split('.')
            module_name, class_name = module_class_part.split('::')
            return module_name, class_name, method_name
        else:
            # This is a standalone function, so we split only by '::'
            module_name, function_name = node_name.split('::')
            return module_name, None, function_name

    @staticmethod
    def get_test_method_prefix():
        return "test_"
