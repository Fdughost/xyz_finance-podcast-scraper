# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

公募基金播客监控系统，用于爬取小宇宙（xiaoyuzhoufm.com）上的播客数据，并生成 Excel 日报。主要监控公募基金公司的官方播客节目。

## 常用命令

```bash
# 运行完整监控流程（爬取 + 存储 + 生成报表）
python main.py

# 仅爬取数据并保存为 JSON
python podcast_crawler.py

# 解析播客 ID（从名称或 URL 批量解析）
python podcast_id_resolver.py --input podcast_list.txt --output data/podcast_id_map_YYYY-MM-DD.json --output-csv data/podcast_id_map_YYYY-MM-DD.csv

# 解析后自动更新 config.json 中的 podcast_id
python podcast_id_resolver.py --input podcast_list.txt --update-config config.json

# 强制刷新缓存重新解析
python podcast_id_resolver.py --input podcast_list.txt --refresh

# 从文本文件提取播客名称并添加到 config.json
python update_config.py --names podcast_list_v2.txt --config config.json
```

## 架构说明

### 数据流

```
config.json（播客列表）
    → podcast_crawler.py（爬取小宇宙页面）
    → data_manager.py（存入 SQLite 数据库）
    → excel_generator.py（生成 Excel 日报）
    → reports/播客监控日报_YYYY-MM-DD.xlsx
```

### 核心模块

- **`main.py`**：主入口，串联爬虫 → 数据库 → Excel 三步流程
- **`podcast_crawler.py`**：`XiaoyuzhouCrawler` 类，抓取小宇宙播客页面。优先从页面内嵌的 `__NEXT_DATA__` JSON 中提取数据，DOM 解析作为备选。播客若无 `podcast_id` 会自动通过搜索引擎解析
- **`data_manager.py`**：`PodcastDataManager` 类，使用 SQLite（`data/podcast_monitor.db`）存储每日快照，支持与前日数据对比
- **`excel_generator.py`**：`PodcastExcelGenerator` 类，将爬取数据输出为格式化 Excel（含中文列名、样式），按订阅数降序排列
- **`report_generator.py`**：`ReportGenerator` 类，生成 Word 格式日报（较少使用，主流程已改为 Excel）
- **`podcast_id_resolver.py`**：独立工具，通过 DuckDuckGo/360/搜狗/Bing 等搜索引擎或小宇宙 App API 将播客名称解析为 `podcast_id`，带本地 JSON 缓存（`data/podcast_id_resolver_cache.json`）
- **`update_config.py`**：辅助脚本，从文本文件批量提取播客名称并追加到 `config.json`

### 配置文件 config.json

每个播客条目结构：

```json
{
  "name": "播客名称",
  "podcast_id": "24位十六进制ID",
  "category": "公募基金 | 泛财经",
  "fund_company_name": "基金公司名称",
  "enabled": true
}
```

`podcast_id` 可留空，爬虫会在运行时通过搜索引擎自动解析（但建议预先填好以提高稳定性）。

### 文件目录

- `data/` - SQLite 数据库、ID 解析结果、缓存
- `reports/` - 生成的 Excel/Word 报表
- `logs/` - 运行日志（`main.log`、`crawler.log`，已 gitignore）

### 依赖

主要依赖：`requests`、`beautifulsoup4`、`pandas`、`openpyxl`、`python-docx`
