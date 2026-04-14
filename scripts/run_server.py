#!/usr/bin/env python3
"""
启动脚本 - Monkey Brain Pipeline API Server
"""

import os
import sys
from app import app
from config import config, Config

def main():
    # 获取环境变量
    env = os.environ.get('FLASK_ENV', 'development')
    
    # 加载配置
    app_config = config.get(env, config['default'])
    
    # 初始化目录
    Config.init_directories()
    
    print(f"🚀 Starting Monkey Brain Pipeline API Server")
    print(f"📁 Environment: {env}")
    print(f"🌐 Host: {app_config.HOST}")
    print(f"🔌 Port: {app_config.PORT}")
    print(f"🐛 Debug: {app_config.DEBUG}")
    print(f"📂 Script Directory: {app_config.SCRIPT_DIR}")
    print(f"📝 Log Directory: {app_config.LOG_DIR}")
    print("=" * 50)
    
    try:
        app.run(
            host=app_config.HOST,
            port=app_config.PORT,
            debug=app_config.DEBUG
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

