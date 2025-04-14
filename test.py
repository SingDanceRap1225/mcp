from openai import OpenAI
import json


def test():
    client = OpenAI(
        api_key="sk-83c16161a4834a06be2f0edafb0f6bdf",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    completion = client.chat.completions.create(
        model="qwen-plus",
        # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': '你是谁?'}],
        stream=False,
        temperature=1,
        top_p=0.5,
    )

    print(json.loads(completion.model_dump_json()))


if __name__ == '__main__':
    test()


