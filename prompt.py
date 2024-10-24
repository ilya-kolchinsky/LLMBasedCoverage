class PromptGenerator(object):
    def __init__(self, code_retriever, tool_use_enabled=False):
        self.code_retriever = code_retriever
        self.tool_use_enabled = tool_use_enabled

    def create_prompt(self, path, current_step):
        origin_function = path[0]
        origin_class_and_method_name = origin_function.function_name \
            if origin_function.class_name is None \
            else f"{origin_function.class_name}.{origin_function.function_name}"
        origin_method_or_function = "function" if origin_function.class_name is None else "method"

        source_function = path[current_step]
        source_class_and_method_name = source_function.function_name \
            if source_function.class_name is None \
            else f"{source_function.class_name}.{source_function.function_name}"
        source_method_or_function = "function" if source_function.class_name is None else "method"

        destination_function = path[current_step+1]
        destination_class_and_method_name = destination_function.function_name \
            if destination_function.class_name is None \
            else f"{destination_function.class_name}.{destination_function.function_name}"
        destination_method_or_function = "function" if source_function.class_name is None else "method"

        if current_step == 0:  # i.e., origin_function == source_function
            origin_function_code = self.code_retriever.retrieve(origin_function)
            prompt = f"Below is the source code of the {origin_method_or_function} '{origin_class_and_method_name}'. " \
                     f"Does '{origin_class_and_method_name}' invoke '{destination_class_and_method_name}' when executed? " \
                     f"Only answer 'yes' or 'no'." \
                     f"\n\n" \
                     f"{origin_function_code}"

        else:  # source_function is a hop in between origin and destination
            source_function_code = self.code_retriever.retrieve(source_function)
            prompt = f"Following the above, below is the source code of the {source_method_or_function} '{source_class_and_method_name}'. " \
                     f"Does '{source_class_and_method_name}' invoke '{destination_class_and_method_name}' when called from '{origin_class_and_method_name}'? " \
                     f"Only answer 'yes' or 'no'." \
                     f"\n\n" \
                     f"{source_function_code}"

        if self.tool_use_enabled:
            prompt += ("\n\nYou have access to a tool called extract_code which gives you the source code of a given function or method. "
                       "The tool accepts the following parameters: "
                       "1) module_name - the module containing the code to be extracted or None if unknown."
                       "2) class_name - the class containing the method to be extracted or None if unknown or if the code to be extracted is a function."
                       "3) method_or_function_name - the name of the method (if class_name is given) or the function (if class_name is not given) to be extracted."
                       "Use this tool if needed.")

        return prompt

    def create_initial_prompt(self, path, current_step):
        # temporary implementation
        return self.create_prompt(path, current_step)

    @staticmethod
    def analyze_llm_reply(reply):
        """
        Returns 'y' if the reply from LLM is positive, 'n' if it is negative, and None if impossible to decide.
        """
        if 'yes' in reply.content.lower():
            return 'y'
        if 'no' in reply.content.lower():
            return 'n'
        # failed to parse the response - let's be safe and assume a positive reply
        return 'y'
