import asyncio
from llm_model.ai_app_test import AIApp
from typing import Optional, List, Dict
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from utills import format_available_tools, handle_tool_call


class MCPClient:
    def __init__(self, llm: AIApp, server_script_path: list[str]):
        # 初始化对话 LLM
        self.llm_app = llm

        # 用于管理异步上下文的退出栈
        self.exit_stack = AsyncExitStack()

        # MCP 客户端会话，以字典形式存储不同服务器的会话信息
        self.mcp_session = {}

        # MCP 服务器脚本路径
        self.server_script_path = server_script_path

        # 可用 MCP tools 列表
        self.available_tools = []

        # tool 与 server 的映射
        self.tool_map = {}

    def get_server_parameters(self, path) -> StdioServerParameters:
        """
        根据服务器脚本文件类型生成启动服务器所需的参数。

        :param path: 服务器脚本文件路径
        :return: 包含服务器启动命令和参数的 StdioServerParameters 对象
        :raises ValueError: 如果脚本文件类型不是 .py 或 .jar
        """
        if path.endswith('.py'):
            command = "python"
            args = [path]
        elif path.endswith('.jar'):
            command = "java"
            args = [
                "-Dfile.encoding=UTF-8",
                "-jar", path,
                "-Dspring.ai.mcp.server.stdio=true",
                "-Dspring.main.web-application-type=none"
            ]
        else:
            raise ValueError("不支持的脚本文件类型，仅支持 .py 或 .jar 文件")

        return StdioServerParameters(command=command, args=args, env=None)

    async def connect_to_mcp_server(self, server_name, path):
        """
        连接到 MCP 服务器，启动服务器并列出可用工具，将工具注入到 LLM 中。

        :param server_name: 服务器名称
        :param path: 服务器脚本文件路径
        """
        # 获取服务器启动参数
        server_params = self.get_server_parameters(path)

        # 启动 MCP 服务器并获取输入输出流
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport

        # 初始化 MCP 客户端会话
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()

        # 把当前 server 的 session 加入到字典，便于后续根据tool寻找server
        self.mcp_session[server_name] = {"session": session, "stdio": stdio, "write": write}

        # 列出 MCP 服务器上的工具
        mcp_response = await session.list_tools()
        tools = mcp_response.tools
        print(f"已连接 MCP 服务器{server_name}，支持以下工具：\n", [tool.name for tool in tools])

        # 格式化可用工具
        format_tools = format_available_tools(mcp_response)
        for format_tool in format_tools:
            self.available_tools.append(format_tool)

        # 构建 tool 与 server 的映射
        for tool in tools:
            self.tool_map[tool.name] = server_name

    def set_llm_tools(self):
        """
        将可用工具注入到 LLM 中。
        """
        if self.available_tools:
            self.llm_app.set_tools(self.available_tools)

    async def process_query(self, query: str):
        """
        处理用户输入的查询，若 LLM 需要调用 MCP 服务器工具，则并发执行工具调用并整合结果。

        :param query: 用户输入的查询语句
        :return: 处理后的响应文本
        """
        # 向 LLM 发送查询并获取流式响应
        response_generator = self.llm_app.generate_response(prompt_index=1, user_input=query)
        if self.llm_app.stream:
            partial_response = ""
            for chunk in response_generator:
                print(chunk,end='', flush=True)
                # partial_response += chunk.choices[0].delta.content
                # yield chunk
                # if "tool_calls" in partial_response:
                #     # 解析所有工具调用
                #     tool_calls = handle_tool_call({"message": {"content": partial_response}})
                #     # 并发执行所有工具调用
                #     tool_results = await self.run_tools_concurrently(tool_calls)
                #     print(f"工具调用结果: {tool_results}")  # 添加日志输出
                #     # 将工具调用结果和初始查询重新发送给 LLM
                #     new_response_generator = self.llm_app.generate_response(
                #         prompt_index=2,
                #         user_input=f"{query}\n{tool_results}"
                #     )
                #     for new_chunk in new_response_generator:
                #         yield new_chunk
                #     break
        # else:
        #     response = response_generator
        #     content = response.choices[0]
        #     if content.finish_reason == "tool_calls":
        #         # 解析所有工具调用
        #         tool_calls = handle_tool_call(content)
        #         # 并发执行所有工具调用
        #         tool_results = await self.run_tools_concurrently(tool_calls)
        #         print(f"工具调用结果: {tool_results}")  # 添加日志输出
        #         # 将工具调用结果和初始查询重新发送给 LLM
        #         new_response = self.llm_app.generate_response(
        #             prompt_index=2,
        #             user_input=f"{query}\n{tool_results}"
        #         )
        #         response_text = new_response.choices[0].message.content
        #         yield response_text
        #     else:
        #         response_text = content.message.content
        #         yield response_text

    async def run_tools_concurrently(self, tool_calls: List[Dict]) -> List[str]:
        """
        并发执行多个工具调用，并处理可能出现的异常。

        :param tool_calls: 包含工具调用信息的字典列表
        :return: 工具调用结果列表
        """
        tasks = []
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get("name")
                # 确定当前工具使用哪一个 server 的 session
                session = self.mcp_session.get(self.tool_map.get(tool_name)).get("session")
                # 创建工具调用任务
                task = session.call_tool(
                    tool_name,
                    tool_call.get("args")
                )
                tasks.append(task)
            except Exception as e:
                print(f"工具 {tool_call['name']} 准备任务失败: {str(e)}")

        # 并发执行所有工具调用任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 处理工具调用失败的情况
                processed_results.append(f"工具 {tool_calls[i]['name']} 调用失败: {str(result)}")
            else:
                print(f"原始工具调用结果: {result}")  # 添加日志输出
                if hasattr(result, 'content') and len(result.content) > 0 and hasattr(result.content[0], 'text'):
                    # 提取工具调用成功的结果
                    processed_results.append(result.content[0].text)
                else:
                    print(f"工具 {tool_calls[i]['name']} 返回结果格式异常: {result}")
                    processed_results.append(f"工具 {tool_calls[i]['name']} 返回结果格式异常")

        return processed_results

    async def chat_loop(self):
        """
        运行交互式聊天循环，接收用户输入并处理查询，直到用户输入 'quit' 退出。
        """
        print("\nMCP 客户端已启动！输入 'quit' 退出")
        while True:
            try:
                # 获取用户输入
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                await self.process_query(query)
                # 处理用户查询
                # async for chunk in self.process_query(query):
                #     print(chunk, end='', flush=True)
                print()
            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")

    async def cleanup(self):
        """
        清理资源，关闭异步上下文。
        """
        await self.exit_stack.aclose()

    async def connect_to_all_servers(self):
        """
        连接到所有 MCP 服务器，并设置 LLM 工具。
        """
        for path in self.server_script_path:
            print(path)
            await self.connect_to_mcp_server(path, path)

        self.set_llm_tools()


async def main():
    # 初始化 LLM
    llm = AIApp(config_file='llm_model/config.ini')

    # 服务器脚本路径列表
    server_script_path = [
        "mcp_server/mcp-server-0.0.1-SNAPSHOT.jar",
        "mcp_server/mcp_server_starter.py"
    ]

    # 创建 MCP 客户端实例
    client = MCPClient(llm=llm, server_script_path=server_script_path)

    try:
        # 连接到所有 MCP 服务器
        await client.connect_to_all_servers()

        # 启动聊天循环
        await client.chat_loop()
    finally:
        # 清理资源
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())