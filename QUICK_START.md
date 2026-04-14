# Monkey Brain 项目 - 新用户快速开始

## 🚀 3分钟快速部署

### 📋 前提条件

- Python 3.7+
- 已安装依赖包：`pip install -r requirements.txt`

### 🔧 部署步骤

**1️⃣ 复制项目文件**
```bash
# 复制到您的用户目录
cp -r /home/xuancheng/monkey_brain_segmentation_pipeline ~/
cp -r /home/xuancheng/CYUPS_HOME-Chimpanzee ~/
```

**2️⃣ 启动服务**
```bash
cd ~/monkey_brain_segmentation_pipeline
python3 app.py
```

**3️⃣ 访问服务**
- 🌐 主服务: http://服务器IP:8000
- 📊 报告查看: http://服务器IP:8000/reports  
- �� API列表: http://服务器IP:8000/tools

### ⚙️ 自定义配置（可选）

如果需要更改端口或其他设置：

```bash
# 运行配置向导
python3 setup_user_config.py

# 然后启动
python3 app.py
```

### 🔍 验证部署

```bash
# 检查服务状态
curl http://localhost:8000/tools

# 应该返回可用工具列表
```

### 🛠️ 常见问题

**端口冲突**: 
```bash
# 方法1: 使用环境变量
MONKEY_BRAIN_PORT=8001 python3 app.py

# 方法2: 运行配置向导选择新端口
python3 setup_user_config.py
```

**权限问题**:
```bash
# 确保项目目录有正确权限
chmod -R 755 ~/monkey_brain_segmentation_pipeline
```

### 📱 一键启动脚本

创建启动脚本：
```bash
cat > start.sh << 'SCRIPT'
#!/bin/bash
cd ~/monkey_brain_segmentation_pipeline
echo "🚀 启动 Monkey Brain 服务..."
python3 app.py
SCRIPT

chmod +x start.sh
./start.sh
```

---

**就是这么简单！** 🎉

详细配置选项请参考 `DEPLOYMENT_GUIDE.md`
