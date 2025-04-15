import asyncio
import os
import sys

import aiohttp
import json

package_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(package_dir)
from mcp_server import CONFIG


# 从api获取天气信息
async def fetch_weather(province: str, city: str) -> str:
    weather_api = CONFIG.get('WeatherServer', 'WEATHER_API')
    url = weather_api + f"&sheng={province}&place={city}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    json_str = await response.text()
                    data = json.loads(json_str)
                    return (f"地点: {data['place']} \n"
                            f"天气状况（白天）: {data['weather1']}\n"
                            f"天气状况（夜晚）: {data['weather2']}\n"
                            f"温度: {data['temperature']}°C\n"
                            f"降水量: {data['precipitation']}\n"
                            f"气压: {data['pressure']} hPa\n"
                            f"湿度: {data['humidity']}%\n"
                            f"风向: {data['windDirection']}\n"
                            f"风向角度: {data['windDirectionDegree']}°\n"
                            f"风速: {data['windSpeed']} m/s\n"
                            f"风力等级: {data['windScale']}\n")
                else:
                    return f"请求失败，状态码: {response.status}"
        except Exception as e:
            return f"请求过程中出现错误: {e}"
if __name__ == '__main__':
    print(asyncio.run(fetch_weather("江苏","南京")))