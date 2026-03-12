# 播客监控与日报系统

一个自动化的公募基金播客数据监控系统，定期抓取各大基金公司的播客数据并生成Excel日报。

## 功能特性

- 🎯 **自动爬取**: 定期抓取25个公募基金公司的播客数据
- 📊 **数据统计**: 订阅数、播放量、互动指标等关键数据
- 📈 **Excel报表**: 自动生成格式化的日报，按订阅数降序排列
- 🗄️ **数据存储**: 本地SQLite数据库存储历史数据
- 🔄 **增量更新**: 支持与昨日数据对比分析

## 支持的播客

目前监控25个公募基金公司的官方播客：

| 基金公司 | 播客名称 |
|---------|---------|
| 华夏基金 | 大方谈钱 |
| 中欧基金 | 中欧基金播客 |
| 富国基金 | 有富同享 |
| 财通基金 | 与财同行 |
| 天弘基金 | 人间钱话 |
| 大成基金 | 深度求真 |
| 广发基金 | 养基方程式 |
| 银华基金 | 基金经理一周论市、莫问钱程 |
| 中泰资管 | 好朋友的播客、好朋友的直播间 |
| 德邦基金 | 德邦基金财经列车 |
| 国投瑞银基金 | 投资心得·基金聊天局、投资心法·基金访谈录 |
| 嘉实基金 | 时间嘉讲 |
| 国泰基金 | 泰客Talk |
| 易方达基金 | 茶水间经济学、财话连篇 |
| 汇添富基金 | 钱途规划局 |
| 兴全基金 | 随基漫步 |
| 鹏华基金 | 鹏然心动 |
| 中金资管 | 话中有金 |
| 华泰证券 | 泰度Voice |
| 蚂蚁财富 | 和盘托出 |
| 雪球财富 | 厚雪长波 |

## 环境要求

- Python 3.8+
- 依赖包见 `requirements.txt`

## 安装使用

1. 克隆仓库
```bash
git clone https://github.com/Fdughost/daily-podcast-news.git
cd daily-podcast-news
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行监控
```bash
python main.py
```

## 输出文件

- **Excel报表**: `reports/播客监控日报_YYYY-MM-DD.xlsx`
- **日志文件**: `logs/main.log`, `logs/crawler.log`
- **数据库**: `data/podcast_monitor.db`

## 项目结构

```
daily-podcast-news/
├── main.py                 # 主入口
├── podcast_crawler.py      # 播客爬虫
├── data_manager.py         # 数据管理
├── excel_generator.py      # Excel生成器
├── report_generator.py     # 报表生成器
├── podcast_id_resolver.py  # ID解析器
├── update_config.py       # 配置更新工具
├── config.json            # 配置文件
├── data/                  # 数据目录
├── reports/               # 报表目录
├── logs/                  # 日志目录
└── README.md              # 说明文档
```

## 配置说明

`config.json` 主要配置项：

- `podcasts`: 播客列表配置
- `crawler_settings`: 爬虫设置（请求延迟、重试次数等）
- `report_settings`: 报表设置（输出目录、是否包含图表等）

## 数据字段

Excel报表包含以下字段：

- 节目名称
- 基金公司
- 订阅数
- 最新单集名称
- 最新单集上线日期
- 最新单集播放数量
- 最新单集评论数
- 最新单集点赞数
- 最新单集收藏数
- 互动指标(点赞+收藏)
- 最新单集时长
- 抓取时间

## 注意事项

- 系统基于小宇宙播客平台API
- 请遵守平台使用规范，合理控制请求频率
- 数据仅供参考，不构成投资建议

## License

MIT License
