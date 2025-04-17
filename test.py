import asyncio
from llm_model.ai_app import AIApp
from typing import Optional, List, Dict
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from utills import format_available_tools, handle_tool_call


class MCPClient:
    def __init__(self, llm: AIApp, server_script_path: str):
        # 初始化对话 LLM
        self.llm_app = llm
        # 用于管理异步上下文的退出栈
        self.exit_stack = AsyncExitStack()
        # MCP 客户端会话，初始化为 None
        self.mcp_session: Optional[ClientSession] = None
        # MCP 服务器脚本路径
        self.server_script_path = server_script_path

    def get_server_parameters(self) -> StdioServerParameters:
        """
        根据服务器脚本文件类型生成启动服务器所需的参数。

        :return: 包含服务器启动命令和参数的 StdioServerParameters 对象
        :raises ValueError: 如果脚本文件类型不是 .py 或 .jar
        """
        if self.server_script_path.endswith('.py'):
            command = "python"
            args = [self.server_script_path]
        elif self.server_script_path.endswith('.jar'):
            command = "java"
            args = [
                "-Dfile.encoding=UTF-8",
                "-jar", self.server_script_path,
                "-Dspring.ai.mcp.server.stdio=true",
                "-Dspring.main.web-application-type=none",
                "-Dlogging.pattern.console="
            ]
        else:
            raise ValueError("不支持的脚本文件类型，仅支持 .py 或 .jar 文件")

        return StdioServerParameters(command=command, args=args, env=None)

    async def connect_to_mcp_server(self):
        """
        连接到 MCP 服务器，启动服务器并列出可用工具，将工具注入到 LLM 中。
        """
        # 获取服务器启动参数
        server_params = self.get_server_parameters()
        # 启动 MCP 服务器并获取输入输出流
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        # 初始化 MCP 客户端会话
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await self.mcp_session.initialize()

        # 列出 MCP 服务器上的工具
        mcp_response = await self.mcp_session.list_tools()
        tools = mcp_response.tools
        print("已连接 MCP 服务器，支持以下工具：\n", [tool.name for tool in tools])
        # 格式化可用工具
        available_tools = format_available_tools(mcp_response)
        # 将可用工具注入到 LLM 中
        self.llm_app.set_tools(available_tools)

    async def process_query(self, query: str) -> str:
        """
        处理用户输入的查询，若 LLM 需要调用 MCP 服务器工具，则并发执行工具调用并整合结果。

        :param query: 用户输入的查询语句
        :return: 处理后的响应文本
        """
        # 向 LLM 发送查询并获取响应
        response = self.llm_app.generate_response(prompt_index=1, user_input=query)
        content = response.choices[0]

        # 如果 LLM 需要调用 MCP 服务器工具
        if content.finish_reason == "tool_calls":
            # 解析所有工具调用
            tool_calls = handle_tool_call(content)
            # 并发执行所有工具调用
            tool_results = await self.run_tools_concurrently(tool_calls)
            print(tool_results)
            # 将工具调用结果和初始查询重新发送给 LLM
            response = self.llm_app.generate_response(
                prompt_index=2,
                user_input=f"{query}\n{tool_results}"
            )

        # 获取最终响应文本
        response_text = response.choices[0].message.content
        return response_text

    async def run_tools_concurrently(self, tool_calls: List[Dict]) -> List[str]:
        """
        并发执行多个工具调用，并处理可能出现的异常。

        :param tool_calls: 包含工具调用信息的字典列表
        :return: 工具调用结果列表
        """
        tasks = []
        for tool_call in tool_calls:
            try:
                # 创建工具调用任务
                task = self.mcp_session.call_tool(
                    tool_call.get("name"),
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
                # 提取工具调用成功的结果
                processed_results.append(result.content[0].text)

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
                # 处理用户查询
                response = await self.process_query(query)
                print(f"\n🤖 AI: {response}")
            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")

    async def cleanup(self):
        """
        清理资源，关闭异步上下文。
        """
        await self.exit_stack.aclose()


async def main():
    # 初始化 LLM
    llm = AIApp(config_file='llm_model/config.ini')
    # 创建 MCP 客户端实例
    client = MCPClient(llm=llm, server_script_path="mcp_server/mcp-server-0.0.1-SNAPSHOT.jar")
    try:
        # 连接到 MCP 服务器
        await client.connect_to_mcp_server()
        # 启动聊天循环
        await client.chat_loop()
    finally:
        # 清理资源
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
