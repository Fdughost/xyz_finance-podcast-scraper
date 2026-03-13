#!/bin/bash
# 播客监控系统定时启动脚本
# 每小时被 launchd 调用一次；10 点后且今日未运行时才真正执行

cd /Users/alexfeng/Documents/Programming/daily-podcast-news
mkdir -p logs

TODAY=$(date +%Y-%m-%d)
HOUR=$(date +%H | sed 's/^0//')   # 去掉前导零，避免八进制问题
SENTINEL="logs/ran_${TODAY}.flag"

# 10 点之前不运行
if [ "$HOUR" -lt 10 ]; then
    exit 0
fi

# 今天已运行过，跳过
if [ -f "$SENTINEL" ]; then
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行播客监控任务" >> logs/launchd.log

/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 main.py

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    touch "$SENTINEL"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 任务完成" >> logs/launchd.log
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 任务失败（exit $EXIT_CODE），下次唤醒将重试" >> logs/launchd.log
fi
