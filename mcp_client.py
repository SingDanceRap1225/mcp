import asyncio
from llm_model.ai_app import AIApp
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from utills import format_available_tools, handle_tool_call


class MCPClient:
    def __init__(self, llm:AIApp, server_script_path:str):
        self.app = llm            # 初始化对话LLM
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
        self.server_script_path = server_script_path

    def get_server_params(self, server_script_path: str):
        """根据server文件类型启动server"""

        if server_script_path.endswith('.py'):
            command = "python"
            args = [server_script_path]
        elif server_script_path.endswith('.jar'):
            command = "java"
            args = ["-Dfile.encoding=UTF-8",
                    "-jar", server_script_path,
                    "-Dspring.ai.mcp.server.stdio=true",
                    "-Dspring.main.web-application-type=none",
                    "-Dlogging.pattern.console="]
        else:
            raise ValueError("不支持的脚本文件类型，仅支持 .py 或 .jar 文件")

        return StdioServerParameters(command=command, args=args, env=None)

    async def connect_to_mcp_server(self):
        """使用LLM查询并调用MCPServer"""

        # 启动MCP server
        server_params = self.get_server_params(self.server_script_path)
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

        # 列出MCPServer上的工具
        mcp_response = await self.session.list_tools()
        tools = mcp_response.tools
        print("已连接MCP服务器，支持以下工具：\n", [tool.name for tool in tools])
        available_tools = format_available_tools(mcp_response)

        # 将可用的MCPServer工具注入LLM
        self.app.set_tools(available_tools)

    async def process_query(self, query: str) -> str:
        """把输入提问提交LLM"""
        response = self.app.generate_response(prompt_index=1, user_input=query)

        content = response.choices[0]
        # LLM需要调用MCP server
        if content.finish_reason == "tool_calls":
            tool_name, tool_args = handle_tool_call(content)

            # 执行MCPServer工具
            print(f"Calling tool {tool_name} with args {tool_args}")
            result = await self.session.call_tool(tool_name, tool_args)
            # 将模型调用的server工具返回结果连同初始提问再喂给大模型
            response = self.app.generate_response(prompt_index=2, user_input=query + "\n" + result.content[0].text)

        response_text = response.choices[0].message.content

        return response_text

    async def chat_loop(self):
        """运行交互式聊天循环"""

        print("\nMCP 客户端已启动！输入 'quit' 退出")
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query) # 发送用户输入到LLM
                print(f"\n🤖 AI: {response}")
            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()


async def main():
    # 初始化LLM
    llm = AIApp(config_file='llm_model/config.ini')

    # LLM和mcp server文件注入到mcp client
    client = MCPClient(llm=llm, server_script_path="mcp_server/mcp_server_starter.py")
    # client = MCPClient(llm=llm, server_script_path="mcp_server/mcp-server-0.0.1-SNAPSHOT.jar")  # 支持jar封装的server
    try:
        # 启动并连接MCP Server
        await client.connect_to_mcp_server()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
