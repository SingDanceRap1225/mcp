import configparser
import os

# 获取 __init__.py 文件所在目录
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, "config.ini")

# 初始化config文件供包内其他方法调用
CONFIG = configparser.ConfigParser()
CONFIG.read(config_path, encoding='utf-8')