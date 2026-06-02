#!/bin/bash
# 武鸣招聘 - 自动部署脚本
# 检测Git更新 → 拉取 → 重启 → 截图验证

cd /home/ubuntu/hermes-web || { echo "目录不存在"; exit 1; }

# 记录当前HEAD
OLD_HEAD=$(git rev-parse HEAD)

# 检查远程更新
git fetch origin master 2>&1 || { echo "fetch失败"; exit 1; }

NEW_HEAD=$(git rev-parse origin/master)

if [ "$OLD_HEAD" = "$NEW_HEAD" ]; then
    echo "没有新版本 ($OLD_HEAD)"
    exit 0
fi

echo "检测到新版本: $OLD_HEAD → $NEW_HEAD"

# 拉取代码
git pull origin master 2>&1 || { echo "pull失败"; exit 1; }

# 杀掉旧进程
PID=$(pgrep -f "main.py" | head -1)
if [ -n "$PID" ]; then
    echo "停止旧进程: $PID"
    kill "$PID" 2>/dev/null
    sleep 2
fi

# 启动新进程
echo "启动新版本..."
nohup /home/ubuntu/.hermes/hermes-agent/venv/bin/python3 main.py > /dev/null 2>&1 &
sleep 3

# 验证
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)
if [ "$HTTP_CODE" = "200" ]; then
    echo "部署成功 (HTTP $HTTP_CODE)"
else
    echo "部署异常 (HTTP $HTTP_CODE)"
fi
