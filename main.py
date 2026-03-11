#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客监控系统主入口 - 增强版
集成爬虫、数据管理和Excel报表生成
"""

import os
import logging
from datetime import datetime
from podcast_crawler import XiaoyuzhouCrawler
from data_manager import PodcastDataManager
from excel_generator import PodcastExcelGenerator

# 配置日志
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_monitor():
    """执行监控任务"""
    logger.info("=" * 50)
    logger.info("开始执行播客监控任务")
    logger.info("=" * 50)
    
    try:
        # 1. 爬取数据
        logger.info("--- 步骤 1/3: 爬取播客数据 ---")
        crawler = XiaoyuzhouCrawler()
        issues = crawler.validate_config()
        if issues:
            logger.warning("检测到配置问题，将跳过无效播客：")
            for item in issues:
                logger.warning(item)
        current_data = crawler.crawl_all_podcasts()
        
        if not current_data:
            logger.warning("未能获取到任何数据，任务终止")
            return
        
        # 2. 保存到数据库
        logger.info("--- 步骤 2/3: 存储数据到数据库 ---")
        db_manager = PodcastDataManager()
        db_manager.save_batch_data(current_data)
        
        # 3. 生成Excel报表
        logger.info("--- 步骤 3/3: 生成Excel报表 ---")
        excel_gen = PodcastExcelGenerator()
        report_path = excel_gen.generate_daily_report(current_data)
        
        logger.info(f"监控任务完成！报表已生成：{report_path}")
        print(f"\n任务成功！报表位置: {report_path}")
        
    except Exception as e:
        logger.error(f"监控任务执行过程中出错: {e}", exc_info=True)

if __name__ == "__main__":
    run_monitor()
