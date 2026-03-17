#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小宇宙播客数据爬虫模块 - 最终精准版 (稳定版)
深度适配小宇宙页面结构，确保抓取到：节目名称、单集标题、上线日期、播放量、评论数和时长。
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import quote

try:
    from podcast_id_resolver import (
        so_search_podcast_urls,
        sogou_search_podcast_urls,
        duckduckgo_search_podcast_urls,
        bing_search_podcast_urls,
        extract_podcast_id_from_url,
        fetch_podcast_title,
        similarity,
    )
except Exception:  # pragma: no cover
    so_search_podcast_urls = None
    sogou_search_podcast_urls = None
    duckduckgo_search_podcast_urls = None
    bing_search_podcast_urls = None
    extract_podcast_id_from_url = None
    fetch_podcast_title = None
    similarity = None

# 配置日志
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'crawler.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._last_request_ts: float = 0.0

    def wait(self):
        if self._min_interval_seconds <= 0:
            return
        now = time.time()
        elapsed = now - self._last_request_ts
        if elapsed < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - elapsed)
        self._last_request_ts = time.time()

class XiaoyuzhouCrawler:
    """小宇宙播客爬虫类"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        crawler_settings = self.config.get('crawler_settings', {}) if isinstance(self.config, dict) else {}
        self.headers = {
            'User-Agent': crawler_settings.get(
                'user_agent',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ),
        }
        self.base_url = "https://www.xiaoyuzhoufm.com"
        self.timeout = int(crawler_settings.get('timeout', 20))
        self.max_retries = int(crawler_settings.get('max_retries', 3))
        request_delay = float(crawler_settings.get('request_delay', 0))
        self.rate_limiter = RateLimiter(min_interval_seconds=request_delay)
        self.session = requests.Session()

    def validate_config(self) -> List[str]:
        issues: List[str] = []
        podcasts = self.config.get('podcasts', []) if isinstance(self.config, dict) else []
        if not isinstance(podcasts, list):
            return ["config.json: 'podcasts' 必须是列表"]
        for idx, p in enumerate(podcasts):
            if not isinstance(p, dict):
                issues.append(f"config.json: podcasts[{idx}] 不是对象")
                continue
            # podcast_id 允许为空：后续会尝试通过节目名称自动解析
        return issues

    def _normalize_date(self, raw: str) -> str:
        raw = (raw or '')
        raw = re.sub(r"[\s\u3000]+", "", raw)
        if not raw:
            return ""

        now = datetime.now()

        # 2026-03-07
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", raw):
            try:
                return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                return raw

        # 2026-03-07T09:55:56.681Z / 2026-03-07T09:55:56+08:00
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}t", raw, flags=re.I):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                try:
                    return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
                except Exception:
                    return raw

        # 2026/3/7
        if re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", raw):
            try:
                return datetime.strptime(raw, "%Y/%m/%d").strftime("%Y-%m-%d")
            except Exception:
                return raw

        # 2026年3月7日
        m = re.match(r"^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日$", raw)
        if m:
            y, mo, d = map(int, m.groups())
            try:
                return datetime(y, mo, d).strftime("%Y-%m-%d")
            except Exception:
                return raw

        # 3月7日
        m = re.match(r"^(\d{1,2})\s*月\s*(\d{1,2})\s*日$", raw)
        if m:
            mo, d = map(int, m.groups())
            try:
                return datetime(now.year, mo, d).strftime("%Y-%m-%d")
            except Exception:
                return raw

        # 相对时间：3天前 / 2小时前 / 昨天
        m = re.match(r"^(\d+)\s*天前$", raw)
        if m:
            days = int(m.group(1))
            return (now - timedelta(days=days)).strftime("%Y-%m-%d")
        m = re.match(r"^(\d+)\s*小时前$", raw)
        if m:
            return now.strftime("%Y-%m-%d")
        m = re.match(r"^(\d+)\s*周前$", raw)
        if m:
            weeks = int(m.group(1))
            return (now - timedelta(days=weeks * 7)).strftime("%Y-%m-%d")
        m = re.match(r"^(\d+)\s*个月前$", raw)
        if m:
            months = int(m.group(1))
            return (now - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        m = re.match(r"^(\d+)\s*年前$", raw)
        if m:
            years = int(m.group(1))
            return (now - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        if raw == "昨天":
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")

        return raw

    def _to_int(self, value, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            try:
                return int(float(value))
            except Exception:
                return default

    def _format_duration(self, seconds) -> str:
        total = self._to_int(seconds, 0)
        if total <= 0:
            return ""
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _extract_next_data(self, soup: BeautifulSoup) -> Dict:
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return {}
        try:
            data = json.loads(script.string)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _extract_podcast_meta_from_next_data(self, next_data: Dict, podcast_id: str) -> Dict:
        if not isinstance(next_data, dict):
            return {}

        best: Dict = {}
        best_score = -1

        def walk(obj):
            nonlocal best, best_score
            if isinstance(obj, dict):
                pid = (obj.get("pid") or "").strip() if isinstance(obj.get("pid"), str) else obj.get("pid")
                if str(pid) == podcast_id and any(k in obj for k in ["title", "subscriptionCount", "description", "author"]):
                    score = sum(1 for k in ["title", "subscriptionCount", "description", "author"] if obj.get(k))
                    if score > best_score:
                        best = obj
                        best_score = score
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(next_data)
        return best if isinstance(best, dict) else {}

    def _extract_latest_episode_from_next_data(self, next_data: Dict) -> Dict:
        if not isinstance(next_data, dict):
            return {}

        hits: List[Dict] = []

        def walk(obj):
            if isinstance(obj, dict):
                if obj.get("eid") and obj.get("title") and any(k in obj for k in ["commentCount", "playCount", "pubDate", "duration"]):
                    hits.append(obj)
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(next_data)
        if not hits:
            return {}

        dedup: Dict[str, Dict] = {}
        for h in hits:
            eid = str(h.get("eid") or "").strip()
            if not eid:
                continue
            if eid not in dedup:
                dedup[eid] = h

        episodes = list(dedup.values())
        if not episodes:
            return {}

        episodes.sort(key=lambda x: str(x.get("pubDate") or ""), reverse=True)
        ep = episodes[0]

        play_count = self._to_int(ep.get("playCount"), 0)
        comment_count = self._to_int(ep.get("commentCount"), 0)
        clap_count = self._to_int(ep.get("clapCount"), 0)
        favorite_count = self._to_int(ep.get("favoriteCount"), 0)

        return {
            "episode_id": str(ep.get("eid") or "").strip(),
            "title": str(ep.get("title") or "").strip(),
            "pub_date": self._normalize_date(str(ep.get("pubDate") or "").strip()),
            "play_count": str(play_count),
            "comment_count": str(comment_count),
            "duration": self._format_duration(ep.get("duration")),
            "clap_count": str(clap_count),
            "favorite_count": str(favorite_count),
            "source": "next_data",
        }

    def _resolve_podcast_id_by_name(self, name: str) -> str:
        name = (name or '').strip()
        if not name:
            return ""

        # 站内网页 search 已不可用(404)，改用公共搜索引擎抓取 podcast 链接再比对标题。
        if so_search_podcast_urls is None or extract_podcast_id_from_url is None:
            return ""

        urls: List[str] = []
        for fn in [duckduckgo_search_podcast_urls, so_search_podcast_urls, sogou_search_podcast_urls, bing_search_podcast_urls]:
            if fn is None:
                continue
            try:
                urls = fn(self.session, name, timeout=self.timeout)
            except Exception:
                urls = []
            if urls:
                break

        if not urls:
            return ""

        best_pid = ""
        best_score = -1.0
        for u in urls[:10]:
            pid = extract_podcast_id_from_url(u)
            if not pid:
                continue
            title = ""
            if fetch_podcast_title is not None:
                try:
                    title = fetch_podcast_title(self.session, u, timeout=self.timeout)
                except Exception:
                    title = ""
            # 优先精确匹配
            if title and title.strip() == name:
                return pid
            score = 0.0
            if similarity is not None and title:
                try:
                    score = float(similarity(name, title))
                except Exception:
                    score = 0.0
            # 兜底：包含匹配
            if score == 0.0 and title:
                if name in title or title in name:
                    score = 0.9
            # 当无法抓到标题时，仍然保留候选（避免因小宇宙反爬/网络原因导致标题为空而解析失败）
            if not title and score == 0.0:
                score = 0.61
            if score > best_score:
                best_score = score
                best_pid = pid

        return best_pid if best_pid else ""

    def _load_config(self, path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {"podcasts": []}

    def get_podcast_info(self, podcast_id: str) -> Optional[Dict]:
        """获取播客详细信息"""
        url = f"{self.base_url}/podcast/{podcast_id}"
        try:
            response = self._request_with_retry(url)
            if response is None:
                return None
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = self._extract_next_data(soup)
            podcast_meta = self._extract_podcast_meta_from_next_data(next_data, podcast_id)
            latest_ep = self._extract_latest_episode_from_next_data(next_data)
            
            # 1. 基础信息
            title = str(podcast_meta.get("title") or "").strip()
            h1 = soup.find('h1')
            if not title and h1:
                title = h1.get_text(strip=True)
            
            subscribers = self._to_int(podcast_meta.get("subscriptionCount"), 0)
            if subscribers <= 0:
                sub_text = soup.get_text()
                sub_match = re.search(r'(\d+)\s*(人订阅|已订阅)', sub_text)
                if sub_match:
                    subscribers = int(sub_match.group(1))
            
            # 2. 单集信息
            if not latest_ep:
                latest_ep = {
                    "episode_id": "",
                    "title": "",
                    "pub_date": "",
                    "play_count": "0",
                    "comment_count": "0",
                    "duration": "",
                    "clap_count": "0",
                    "favorite_count": "0",
                    "source": "dom_fallback",
                }
            
            # 寻找单集标题
            if latest_ep.get("source") != "next_data":
                for a in soup.find_all('a', href=re.compile(r'/episode/')):
                    t = a.get_text(strip=True)
                    if t and len(t) > 2:
                        if t.isdigit():
                            continue
                        latest_ep['title'] = t.split('\n')[0]

                        href = a.get("href") or ""
                        m_ep = re.search(r"/episode/([a-f0-9]{24})", href, flags=re.I)
                        if m_ep:
                            latest_ep["episode_id"] = m_ep.group(1)
                        
                        # 寻找该链接周围的信息
                        parent = a.find_parent('div')
                        if not parent:
                            parent = a.parent
                        
                        if parent:
                            # 日期
                            time_tag = parent.find('time')
                            if time_tag:
                                latest_ep['pub_date'] = self._normalize_date(time_tag.get_text(strip=True))
                            
                            # 播放量、评论数、时长
                            text_parts = [s.strip() for s in parent.stripped_strings]
                            for text in text_parts:
                                if '播放' in text:
                                    m = re.search(r'(\d+(\.\d+)?[wk]?)', text)
                                    if m:
                                        latest_ep['play_count'] = m.group(1)
                                elif '评论' in text:
                                    m = re.search(r'(?:评论\s*(\d+))|(?:(\d+)\s*评论)', text)
                                    if m:
                                        latest_ep['comment_count'] = m.group(1) or m.group(2) or "0"
                                elif re.match(r'^\d+:\d+$', text) or '分钟' in text:
                                    latest_ep['duration'] = text

                            if latest_ep['play_count'] == "0":
                                for text in text_parts:
                                    if re.match(r'^\d+(\.\d+)?[wk]?$', text):
                                        latest_ep['play_count'] = text
                                        break
                        
                        if latest_ep['title']:
                            break

            # 3. 辅助信息
            author = str(podcast_meta.get("author") or "").strip()
            for span in soup.find_all('span'):
                if author:
                    break
                if '主播' in span.get_text() or '主理人' in span.get_text():
                    author = span.get_text(strip=True).replace('主播', '').replace('主理人', '').strip(':').strip('：')
                    break
            
            description = str(podcast_meta.get("description") or "").strip()
            if not description:
                desc_tag = soup.find('section') or soup.find('div', class_=re.compile(r'description', re.I))
                if desc_tag:
                    description = desc_tag.get_text(strip=True)

            result = {
                "podcast_id": podcast_id,
                "title": title,
                "author": author,
                "subscribers": subscribers,
                "description": description,
                "latest_episode_title": latest_ep['title'],
                "latest_episode_date": self._normalize_date(latest_ep['pub_date']),
                "latest_episode_play": latest_ep['play_count'],
                "latest_episode_comment": latest_ep['comment_count'],
                "latest_episode_clap": latest_ep.get("clap_count", "0"),
                "latest_episode_favorite": latest_ep.get("favorite_count", "0"),
                "latest_episode_interaction": str(
                    self._to_int(latest_ep.get("clap_count", 0), 0) + self._to_int(latest_ep.get("favorite_count", 0), 0)
                ),
                "latest_episode_duration": latest_ep['duration'],
                "latest_episode": {
                    "episode_id": latest_ep.get("episode_id", ""),
                    "title": latest_ep['title'],
                    "pub_date": self._normalize_date(latest_ep['pub_date']),
                    "play_count": latest_ep['play_count'],
                    "comment_count": latest_ep['comment_count'],
                    "duration": latest_ep['duration'],
                    "clap_count": latest_ep.get("clap_count", "0"),
                    "favorite_count": latest_ep.get("favorite_count", "0"),
                    "source": latest_ep.get("source", "dom_fallback"),
                },
                "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            return result

        except Exception as e:
            logger.error(f"解析播客 {podcast_id} 出错: {e}")
            return None

    def _request_with_retry(self, url: str) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for attempt in range(max(1, self.max_retries)):
            try:
                self.rate_limiter.wait()
                response = self.session.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                if attempt >= max(1, self.max_retries) - 1:
                    break
                backoff = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(backoff)

        logger.error(f"请求失败: {url}, error: {last_error}")
        return None

    def crawl_all_podcasts(self) -> List[Dict]:
        results = []
        for p in self.config.get('podcasts', []):
            if not p.get('enabled', True): continue
            podcast_name = (p.get('name') or '').strip()
            podcast_id = (p.get('podcast_id') or '').strip()

            # 兼容：podcast_id 可能被填成完整 URL 或包含 'podcast/' 前缀
            if podcast_id:
                m = re.search(r"([a-f0-9]{24})", podcast_id, flags=re.I)
                if m:
                    podcast_id = m.group(1)
                    p['podcast_id'] = podcast_id
            if not podcast_id:
                logger.info(f"podcast_id 缺失，尝试通过名称解析: {podcast_name}")
                podcast_id = self._resolve_podcast_id_by_name(podcast_name)
                if podcast_id:
                    p['podcast_id'] = podcast_id
                    logger.info(f"解析成功: {podcast_name} -> {podcast_id}")
                else:
                    logger.warning(f"跳过: {podcast_name} (缺少 podcast_id 且解析失败)")
                    continue
            logger.info(f"正在抓取: {p.get('name')}")
            info = self.get_podcast_info(podcast_id)
            if info:
                if not info.get('title'): info['title'] = p.get('name')
                info['category'] = p.get('category', '未分类')
                info['config_name'] = p.get('name')
                info['institution_name'] = p.get('institution_name', p.get('fund_company_name', p.get('fund_company', '')))
                results.append(info)
                logger.info(f"成功: {info['title']}, 播放: {info['latest_episode_play']}, 最新集: {info['latest_episode_title'][:20]}")
        return results

    def save_results(self, results: List[Dict]):
        today = datetime.now().strftime('%Y-%m-%d')
        os.makedirs('data', exist_ok=True)
        with open(f'data/podcast_data_{today}.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawler = XiaoyuzhouCrawler()
    data = crawler.crawl_all_podcasts()
    crawler.save_results(data)
