import os
from openai import OpenAI

client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key="sk-83c16161a4834a06be2f0edafb0f6bdf",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

completion = client.chat.completions.create(
    model="qwen-plus",  # 此处以qwen-plus为例，您可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁？"}
    ],
    stream=True
)

full_content = ""
print("流式输出内容为：")
for chunk in completion:
    # 如果stream_options.include_usage为True，则最后一个chunk的choices字段为空列表，需要跳过（可以通过chunk.usage获取 Token 使用量）
    if chunk.choices:
        full_content += chunk.choices[0].delta.content
        print(chunk.choices[0].delta.content, end='', flush=True)
print(f"完整内容为：{full_content}")