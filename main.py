from llm_model.ai_app import AIApp

if __name__ == "__main__":
    app = AIApp('llm_model/config.ini')

    # 第一个提示模板对应的用户输入
    user_input1 = "明天南京天气"
    response1 = app.generate_response(1, user_input1)
    if response1:
        print(f"使用提示模板1和输入 '{user_input1}' 的回复: {response1}")

