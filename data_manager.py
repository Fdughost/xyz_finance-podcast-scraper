#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客数据存储和历史对比模块
使用SQLite数据库存储历史数据，支持数据对比分析
"""

import sqlite3
import json
import os
import re
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PodcastDataManager:
    """播客数据管理类"""
    
    def __init__(self, db_path: str = 'data/podcast_monitor.db'):
        """
        初始化数据管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建播客快照表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS podcast_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                podcast_id TEXT NOT NULL,
                podcast_name TEXT NOT NULL,
                category TEXT,
                subscribers INTEGER,
                description TEXT,
                latest_episode_id TEXT,
                latest_episode_title TEXT,
                crawl_date DATE NOT NULL,
                crawl_time DATETIME NOT NULL,
                raw_data TEXT,
                UNIQUE(podcast_id, crawl_date)
            )
        ''')
        
        # 创建单集快照表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS episode_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                podcast_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                episode_title TEXT,
                play_count INTEGER,
                crawl_date DATE NOT NULL,
                crawl_time DATETIME NOT NULL,
                UNIQUE(episode_id, crawl_date)
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_podcast_date 
            ON podcast_snapshots(podcast_id, crawl_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_episode_date 
            ON episode_snapshots(episode_id, crawl_date)
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def _parse_play_count(self, value) -> int:
        """将播放量字段尽量解析为整数（支持 '1.2w' / '3k' / '123' 等）"""
        try:
            if value is None:
                return 0
            if isinstance(value, (int, float)):
                return int(value)
            s = str(value).strip().lower()
            if not s:
                return 0
            m = None
            # 允许 1.2w / 1w / 8000 / 3k
            m = re.match(r'^(\d+(?:\.\d+)?)([wk])?$', s)
            if not m:
                # 尝试从混合文本中提取数字
                m = re.search(r'(\d+(?:\.\d+)?)([wk])?', s)
            if not m:
                return 0
            num = float(m.group(1))
            unit = (m.group(2) or '').lower()
            if unit == 'w':
                num *= 10000
            elif unit == 'k':
                num *= 1000
            return int(num)
        except Exception:
            return 0

    def save_podcast_data(self, podcast_data: Dict) -> bool:
        """
        保存播客数据到数据库
        
        Args:
            podcast_data: 播客数据字典
            
        Returns:
            是否保存成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            crawl_time = datetime.now(tz=BEIJING_TZ)
            crawl_date = crawl_time.date()
            
            # 保存播客快照
            latest_episode = podcast_data.get('latest_episode', {}) if isinstance(podcast_data.get('latest_episode', {}), dict) else {}
            
            cursor.execute('''
                INSERT OR REPLACE INTO podcast_snapshots 
                (podcast_id, podcast_name, category, subscribers, description,
                 latest_episode_id, latest_episode_title, crawl_date, crawl_time, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                podcast_data.get('podcast_id'),
                podcast_data.get('config_name') or podcast_data.get('title'),
                podcast_data.get('category'),
                podcast_data.get('subscribers', 0),
                podcast_data.get('description', ''),
                latest_episode.get('episode_id', ''),
                latest_episode.get('title') or podcast_data.get('latest_episode_title', ''),
                crawl_date,
                crawl_time,
                json.dumps(podcast_data, ensure_ascii=False)
            ))
            
            # 保存单集快照（如果有单集列表）
            episodes = podcast_data.get('episodes', []) if isinstance(podcast_data.get('episodes', []), list) else []
            for episode in episodes[:5]:  # 只保存最近5期的数据
                cursor.execute('''
                    INSERT OR IGNORE INTO episode_snapshots
                    (podcast_id, episode_id, episode_title, play_count, crawl_date, crawl_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    podcast_data.get('podcast_id'),
                    episode.get('episode_id'),
                    episode.get('title', ''),
                    self._parse_play_count(episode.get('play_count', 0)),
                    crawl_date,
                    crawl_time
                ))
            
            conn.commit()
            conn.close()
            logger.info(f"成功保存播客数据: {podcast_data.get('config_name')}")
            return True
            
        except Exception as e:
            logger.error(f"保存播客数据失败: {e}")
            return False
    
    def save_batch_data(self, podcast_list: List[Dict]) -> int:
        """
        批量保存播客数据
        
        Args:
            podcast_list: 播客数据列表
            
        Returns:
            成功保存的数量
        """
        if not podcast_list:
            return 0
        success_count = 0
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            crawl_time = datetime.now(tz=BEIJING_TZ)
            crawl_date = crawl_time.date()

            for podcast_data in podcast_list:
                try:
                    podcast_id = (podcast_data.get('podcast_id') or '').strip()
                    if not podcast_id:
                        continue
                    latest_episode = podcast_data.get('latest_episode', {}) if isinstance(podcast_data.get('latest_episode', {}), dict) else {}
                    try:
                        subscribers = int(podcast_data.get('subscribers', 0) or 0)
                    except Exception:
                        subscribers = 0
                    cursor.execute('''
                        INSERT OR REPLACE INTO podcast_snapshots 
                        (podcast_id, podcast_name, category, subscribers, description,
                         latest_episode_id, latest_episode_title, crawl_date, crawl_time, raw_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        podcast_id,
                        podcast_data.get('config_name') or podcast_data.get('title'),
                        podcast_data.get('category'),
                        subscribers,
                        podcast_data.get('description', ''),
                        latest_episode.get('episode_id', ''),
                        latest_episode.get('title') or podcast_data.get('latest_episode_title', ''),
                        crawl_date,
                        crawl_time,
                        json.dumps(podcast_data, ensure_ascii=False)
                    ))
                    success_count += 1
                except Exception as e:
                    logger.error(f"保存播客数据失败: {e}")

            try:
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        finally:
            conn.close()

        return success_count
    
    def get_latest_snapshot(self, podcast_id: str) -> Optional[Dict]:
        """
        获取播客的最新快照
        
        Args:
            podcast_id: 播客ID
            
        Returns:
            播客数据字典，不存在返回None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM podcast_snapshots
                WHERE podcast_id = ?
                ORDER BY crawl_date DESC
                LIMIT 1
            ''', (podcast_id,))
            
            row = cursor.fetchone()
            result = self._row_to_dict(cursor, row) if row else None
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"获取最新快照失败: {e}")
            return None
    
    def get_snapshot_by_date(self, podcast_id: str, date: str) -> Optional[Dict]:
        """
        获取指定日期的播客快照
        
        Args:
            podcast_id: 播客ID
            date: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            播客数据字典，不存在返回None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM podcast_snapshots
                WHERE podcast_id = ? AND crawl_date = ?
            ''', (podcast_id, date))
            
            row = cursor.fetchone()
            result = self._row_to_dict(cursor, row) if row else None
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"获取指定日期快照失败: {e}")
            return None
    
    def compare_with_yesterday(self, podcast_id: str) -> Optional[Dict]:
        """
        对比今天和昨天的数据变化
        
        Args:
            podcast_id: 播客ID
            
        Returns:
            包含对比结果的字典
        """
        try:
            today = datetime.now(tz=BEIJING_TZ).date()
            yesterday = today - timedelta(days=1)
            
            today_data = self.get_snapshot_by_date(podcast_id, str(today))
            yesterday_data = self.get_snapshot_by_date(podcast_id, str(yesterday))
            
            if not today_data:
                logger.warning(f"未找到今天的数据: {podcast_id}")
                return None
            
            comparison = {
                'podcast_id': podcast_id,
                'podcast_name': today_data.get('podcast_name'),
                'today': {
                    'date': str(today),
                    'subscribers': today_data.get('subscribers', 0),
                    'latest_episode_id': today_data.get('latest_episode_id', '')
                },
                'yesterday': {
                    'date': str(yesterday),
                    'subscribers': yesterday_data.get('subscribers', 0) if yesterday_data else 0,
                    'latest_episode_id': yesterday_data.get('latest_episode_id', '') if yesterday_data else ''
                },
                'changes': {}
            }
            
            # 计算变化
            if yesterday_data:
                subscriber_change = today_data.get('subscribers', 0) - yesterday_data.get('subscribers', 0)
                comparison['changes']['subscribers'] = subscriber_change
                today_ep_id = (today_data.get('latest_episode_id') or '').strip()
                yday_ep_id = (yesterday_data.get('latest_episode_id') or '').strip()
                if today_ep_id and yday_ep_id:
                    comparison['changes']['has_new_episode'] = (today_ep_id != yday_ep_id)
                else:
                    today_title = (today_data.get('latest_episode_title') or '').strip()
                    yday_title = (yesterday_data.get('latest_episode_title') or '').strip()
                    comparison['changes']['has_new_episode'] = (bool(today_title) and bool(yday_title) and today_title != yday_title)
            else:
                comparison['changes']['subscribers'] = 0
                comparison['changes']['has_new_episode'] = False
            
            return comparison
            
        except Exception as e:
            logger.error(f"对比数据失败: {e}")
            return None
    
    def get_all_latest_snapshots(self) -> List[Dict]:
        """
        获取所有播客的最新快照
        
        Returns:
            播客数据列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM podcast_snapshots
                WHERE crawl_date = (
                    SELECT MAX(crawl_date) FROM podcast_snapshots
                )
                ORDER BY podcast_name
            ''')
            
            rows = cursor.fetchall()
            results = [self._row_to_dict(cursor, row) for row in rows]
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"获取所有最新快照失败: {e}")
            return []
    
    def get_comparison_report(self) -> List[Dict]:
        """
        生成所有播客的对比报告
        
        Returns:
            对比报告列表
        """
        latest_snapshots = self.get_all_latest_snapshots()
        report = []
        
        for snapshot in latest_snapshots:
            podcast_id = snapshot.get('podcast_id')
            comparison = self.compare_with_yesterday(podcast_id)
            if comparison:
                report.append(comparison)
        
        return report
    
    def _row_to_dict(self, cursor, row) -> Dict:
        """将数据库行转换为字典"""
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))
    
    def get_history_trend(self, podcast_id: str, days: int = 7) -> List[Dict]:
        """
        获取播客的历史趋势数据
        
        Args:
            podcast_id: 播客ID
            days: 查询天数
            
        Returns:
            历史数据列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            end_date = datetime.now(tz=BEIJING_TZ).date()
            start_date = end_date - timedelta(days=days-1)
            
            cursor.execute('''
                SELECT crawl_date, subscribers, latest_episode_id
                FROM podcast_snapshots
                WHERE podcast_id = ? AND crawl_date BETWEEN ? AND ?
                ORDER BY crawl_date
            ''', (podcast_id, str(start_date), str(end_date)))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'date': row[0],
                    'subscribers': row[1],
                    'latest_episode_id': row[2]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"获取历史趋势失败: {e}")
            return []


def main():
    """测试函数"""
    logging.basicConfig(level=logging.INFO)
    
    # 测试数据管理器
    manager = PodcastDataManager()
    
    # 读取今天的爬取数据
    today = datetime.now(tz=BEIJING_TZ).strftime('%Y-%m-%d')
    data_file = f'data/podcast_data_{today}.json'
    
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            podcast_list = json.load(f)
        
        # 保存到数据库
        success_count = manager.save_batch_data(podcast_list)
        logger.info(f"成功保存 {success_count} 条数据到数据库")
        
        # 生成对比报告
        report = manager.get_comparison_report()
        logger.info(f"生成对比报告，包含 {len(report)} 个播客")
        
        for item in report:
            logger.info(f"\n播客: {item['podcast_name']}")
            logger.info(f"  订阅数变化: {item['changes']['subscribers']:+d}")
            logger.info(f"  是否有新节目: {'是' if item['changes']['has_new_episode'] else '否'}")
    else:
        logger.warning(f"未找到今天的数据文件: {data_file}")


if __name__ == '__main__':
    main()
