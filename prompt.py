class PromptGenerator(object):
    def __init__(self, code_retriever):
        self.__code_retriever = code_retriever

    def create_prompt(self, path, current_step):
        origin_function = path[0]
        source_function = path[current_step]
        destination_function = path[current_step+1]

        if current_step == 0:  # i.e., origin_function == source_function
            origin_function_code = self.__code_retriever.retrieve(origin_function)
            return f"Below is the source code of the function {origin_function.function_name}. " \
                   f"Does {origin_function.function_name} invoke {destination_function.function_name} when executed? " \
                   f"Only answer 'yes' or 'no'." \
                   f"\n\n" \
                   f"{origin_function_code}"

        # source_function is a hop in between origin and destination
        source_function_code = self.__code_retriever.retrieve(source_function)
        return f"Additionally, here is the source code of the function {source_function.function_name}. " \
               f"Does {source_function.function_name} invoke {destination_function.function_name} when called from {origin_function.function_name} as determined above? " \
               f"Only answer 'yes' or 'no'." \
               f"\n\n" \
               f"{source_function_code}"

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
        return None
