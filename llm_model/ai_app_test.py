import configparser
from openai import OpenAI


class AIApp:
    def __init__(self, config_file, tools: list = None):
        self.config = configparser.ConfigParser()
        try:
            self.config.read(config_file, encoding='utf-8')
            self.api_key = self.config.get('API', 'api_key')
            self.base_url = self.config.get('API', 'base_url')
            self.model = self.config.get('API', 'model')
            self.temperature = float(self.config.get('API', 'temperature'))
            self.top_p = float(self.config.get('API', 'top_p'))
            self.stream = self.config.getboolean('API', 'stream')
            self.tools = tools  # 可用的MCP Server，如果没有就是普通对话模型
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            print(f"配置文件读取错误: {e}")
        except Exception as e:
            print(f"初始化LLM时发生错误: {e}")


    def _generate_non_stream_response(self, user_input, prompt_index=1):
        system_prompt_key = f'system_prompt{prompt_index}'
        try:
            system_prompt = self.config.get('PROMPTS', system_prompt_key)
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_input}
            ]
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                temperature=self.temperature,
                top_p=self.top_p,
                tools=self.tools,
                parallel_tool_calls=True
            )
            return completion
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            print(f"未找到对应的提示模板: {e}")
            return None
        except Exception as e:
            print(f"生成回复时发生错误: {e}")
            return None

    def _generate_stream_response(self, user_input, prompt_index=1):
        system_prompt_key = f'system_prompt{prompt_index}'
        try:
            system_prompt = self.config.get('PROMPTS', system_prompt_key)
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_input}
            ]
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=self.temperature,
                top_p=self.top_p,
                tools=self.tools,
                parallel_tool_calls=True
            )
            response_text = ''
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    response_text += chunk.choices[0].delta.content
                    yield chunk.choices[0].delta.content
            return response_text
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            print(f"未找到对应的提示模板: {e}")
            return None
        except Exception as e:
            print(f"生成回复时发生错误: {e}")
            return None

    def generate_response(self, user_input, prompt_index=1):
        '''必须流式和非流式输出分开处理，不然yield会引起返回对象不管怎样都为generator'''
        if self.stream:
            return self._generate_stream_response(user_input, prompt_index)
        else:
            return self._generate_non_stream_response(user_input, prompt_index)

    def set_tools(self, tools: list):
        self.tools = tools


if __name__ == '__main__':
    llm = AIApp(config_file="config.ini")
    user_input = '你是谁'

    if llm.stream:
        try:
            response_generator = llm.generate_response(user_input)
            print("流式输出结果:")
            for chunk in response_generator:
                print(chunk, end='', flush=True)
            print()
        except Exception as e:
            print(f"测试过程中出现错误: {e}")
    else:
        try:
            response = llm.generate_response(user_input)
            if response is not None:
                print("非流式输出结果:")
                print(response.choices[0].message.content)
            else:
                print("未获取到有效响应")
        except Exception as e:
            print(f"测试过程中出现错误: {e}")
