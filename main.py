#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客监控系统主入口 - 增强版
集成爬虫、数据管理和Excel报表生成
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
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

RUN_SUMMARY_PATH = 'data/run_summary.json'
MAX_HISTORY = 30  # 最多保留最近 30 次运行记录


def _load_run_history() -> list:
    try:
        with open(RUN_SUMMARY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_run_history(history: list):
    os.makedirs('data', exist_ok=True)
    with open(RUN_SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)


def run_monitor():
    """执行监控任务"""
    start_time = datetime.now(tz=BEIJING_TZ)
    run_record = {
        'run_at': start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'running',
        'success_count': 0,
        'failed_count': 0,
        'skipped_count': 0,
        'failed_podcasts': [],
        'report_path': None,
        'error': None,
        'duration_seconds': None,
    }

    logger.info("=" * 60)
    logger.info(f"开始执行播客监控任务  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        # 1. 爬取数据
        logger.info("--- 步骤 1/3: 爬取播客数据 ---")
        crawler = XiaoyuzhouCrawler()

        issues = crawler.validate_config()
        if issues:
            logger.warning("检测到配置问题，将跳过无效播客：")
            for item in issues:
                logger.warning(f"  {item}")

        # 统计配置中启用的播客总数
        all_podcasts = crawler.config.get('podcasts', []) if isinstance(crawler.config, dict) else []
        enabled_podcasts = [p for p in all_podcasts if p.get('enabled', True)]
        expected_count = len(enabled_podcasts)
        logger.info(f"配置中共有 {expected_count} 个启用播客")

        current_data = crawler.crawl_all_podcasts()

        # 对比预期数量，找出缺失的播客
        fetched_ids = {d.get('podcast_id') for d in current_data}
        for p in enabled_podcasts:
            pid = (p.get('podcast_id') or '').strip()
            name = p.get('name', '')
            if pid and pid not in fetched_ids:
                run_record['failed_podcasts'].append({'name': name, 'podcast_id': pid})
                logger.warning(f"  [缺失] {name} ({pid}) — 未返回数据")
            elif not pid:
                run_record['skipped_count'] += 1

        run_record['success_count'] = len(current_data)
        run_record['failed_count'] = len(run_record['failed_podcasts'])

        logger.info(
            f"爬取完成：成功 {run_record['success_count']} / "
            f"失败 {run_record['failed_count']} / "
            f"跳过(无ID) {run_record['skipped_count']} / "
            f"共 {expected_count}"
        )

        if not current_data:
            run_record['status'] = 'failed'
            run_record['error'] = '未能获取到任何数据'
            logger.error("未能获取到任何数据，任务终止")
            return

        # 2. 保存到数据库
        logger.info("--- 步骤 2/3: 存储数据到数据库 ---")
        db_manager = PodcastDataManager()
        db_manager.save_batch_data(current_data)
        logger.info(f"已写入数据库：{len(current_data)} 条记录")

        # 3. 生成Excel报表
        logger.info("--- 步骤 3/3: 生成Excel报表 ---")
        excel_gen = PodcastExcelGenerator()
        report_path = excel_gen.generate_daily_report(current_data)
        run_record['report_path'] = report_path

        elapsed = (datetime.now(tz=BEIJING_TZ) - start_time).total_seconds()
        run_record['duration_seconds'] = round(elapsed, 1)
        run_record['status'] = 'success' if run_record['failed_count'] == 0 else 'partial'

        logger.info("=" * 60)
        logger.info(f"监控任务完成！报表：{report_path}  耗时：{elapsed:.1f}s")
        if run_record['failed_podcasts']:
            logger.warning(f"以下 {run_record['failed_count']} 个播客未获取到数据：")
            for fp in run_record['failed_podcasts']:
                logger.warning(f"  - {fp['name']} ({fp['podcast_id']})")
        logger.info("=" * 60)

    except Exception as e:
        elapsed = (datetime.now(tz=BEIJING_TZ) - start_time).total_seconds()
        run_record['status'] = 'error'
        run_record['error'] = str(e)
        run_record['duration_seconds'] = round(elapsed, 1)
        logger.error(f"监控任务执行过程中出错: {e}", exc_info=True)

    finally:
        if run_record['duration_seconds'] is None:
            run_record['duration_seconds'] = round((datetime.now(tz=BEIJING_TZ) - start_time).total_seconds(), 1)
        history = _load_run_history()
        history.append(run_record)
        _save_run_history(history)
        logger.info(f"运行记录已追加到 {RUN_SUMMARY_PATH}  状态: {run_record['status']}")


if __name__ == "__main__":
    run_monitor()
