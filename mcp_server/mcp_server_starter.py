import asyncio

from mcp.server.fastmcp import FastMCP
import weather_server


# 初始化MCP服务器
mcp = FastMCP("MCPServer")

@mcp.tool(name="查询当前天气", description="查询当前天气，需要省份和城市")
async def quary_weather(province: str, city: str) -> str:
    weather_message = await weather_server.fetch_weather(province, city)
    print(weather_message)
    return weather_message

if __name__ == '__main__':
    # print(asyncio.run(weather_server.fetch_weather("江苏","南京")))

    # 客户端必须在启动时同时启动当前这个脚本，否则无法顺利通信。这是因为 stdio 模式是一种本地进程间通信（IPC，Inter-Process Communication）方式，
    # 它需要服务器作为子进程运行，并通过标准输入输出（stdin/stdout）进行数据交换
    mcp.run(transport='stdio')







