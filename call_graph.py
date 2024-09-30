import os
import subprocess
import networkx as nx

from afunc import AFunc


class CallGraphCreator(object):
    def __init__(self, source_dir=None, test_dir=None, output_dir=None, dot_file_path=None):
        if dot_file_path is None:
            # graph not yet created, create it now
            dot_file_path = self._create_graph(source_dir, test_dir, output_dir)
        self.__graph = self.__load_graph(dot_file_path)

    def _create_graph(self, source_dir, test_dir, output_dir):
        output_file_path = os.path.join(output_dir, "callgraph.dot")
        command_line = self._create_command_line_tool(source_dir, test_dir, output_file_path)
        print(subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout.read())
        return output_file_path

    def __get_node_attr_dict(self):
        return self.__graph._node

    @staticmethod
    def __load_graph(dot_file):
        with open(dot_file, 'r') as f:
            graph = nx.drawing.nx_pydot.read_dot(f)
        return graph

    def get_node_by_function_name(self, afunc):
        for node_id, node in self.__get_node_attr_dict().items():
            if node.get("nname", "").strip("'\"") == afunc.node_name:
                return node_id
        return None

    @staticmethod
    def __filter_duplicate_paths(paths):
        unique_paths = set(tuple(path) for path in paths)
        return [list(p) for p in unique_paths]

    def find_all_test_paths(self, afunc):
        """
        Find all paths that lead to the target function from a test method.
        """
        target_node = self.get_node_by_function_name(afunc)
        if target_node is None:
            raise Exception(f"Node '{afunc.node_name}' not found in the graph.")

        paths = []

        for node_id, node in self.__get_node_attr_dict().items():
            curr_afunc = AFunc(node_name=node.get("nname", "").strip("'\""))
            if not curr_afunc.function_name.startswith(AFunc.get_test_method_prefix()):
                continue
            if node_id == target_node:
                continue
            try:
                for path in nx.all_simple_paths(self.__graph, source=node_id, target=target_node):
                    paths.append(path)
            except nx.NetworkXNoPath:
                continue

        return [[AFunc(node_name=self.__get_node_attr_dict()[node_id]["nname"].strip("'\"")) for node_id in p]
                for p in self.__filter_duplicate_paths(paths)]

    def _create_command_line_tool(self, source_dir, test_dir, output_file_path):
        raise NotImplementedError()


class Code2FlowCallGraphCreator(CallGraphCreator):
    def _create_command_line_tool(self, source_dir, test_dir, output_file_path):
        return f"code2flow -o {output_file_path} --language py {source_dir} {test_dir}"

    def _create_graph(self, source_dir, test_dir, output_dir):
        output_file_path = super()._create_graph(source_dir, test_dir, output_dir)
        # due to an annoying bug in pydot, a hack is required here
        self.__replace_in_file(output_file_path, 'name="', 'nname="')
        return output_file_path

    @staticmethod
    def __replace_in_file(file_path, old, new, chunk_size=1024 * 1024):
        temp_file = file_path + ".tmp"

        with open(file_path, 'r', encoding='utf-8') as infile, open(temp_file, 'w', encoding='utf-8') as outfile:
            while True:
                chunk = infile.read(chunk_size)
                if not chunk:
                    break
                outfile.write(chunk.replace(old, new))

        # Replace the original file with the updated one
        os.replace(temp_file, file_path)


if __name__ == "__main__":
    graph_creator = Code2FlowCallGraphCreator(dot_file_path=r"C:\Users\ilyak\PycharmProjects\callgraph.dot")
    target_function = AFunc(function_name="ensure_type", class_name=None, module_name="manager")
    test_paths = graph_creator.find_all_test_paths(target_function)
    print(*test_paths, sep='\n')
