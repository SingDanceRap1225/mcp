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

    def generate_response(self, user_input, prompt_index=1):
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
                stream=self.stream,
                temperature=self.temperature,
                top_p=self.top_p,
                tools=self.tools
            )
            # if self.stream:
            #     response_text = ''
            #     for chunk in completion:
            #         if chunk.choices[0].delta.content:
            #             response_text += chunk.choices[0].delta.content
            #     return response_text
            # print(completion)
            # return completion.choices[0].message.content
            return completion
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            print(f"未找到对应的提示模板: {e}")
            return None
        except Exception as e:
            print(f"生成回复时发生错误: {e}")
            return None

    def set_tools(self, tools: list):
        self.tools = tools

if __name__ == '__main__':
    llm = AIApp(config_file="config.ini")
    print(llm.generate_response("你是谁").choices[0].message.content)
