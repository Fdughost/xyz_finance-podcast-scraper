#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import hashlib
import json
import logging
import os
import random
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PODCAST_URL_RE = re.compile(r"https?://www\.xiaoyuzhoufm\.com/podcast/([a-f0-9]{24})", re.I)


# ---------------------------------------------------------------------------
# 名称规范化 & 相似度
# ---------------------------------------------------------------------------

def normalize_name(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.strip().lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    for ch in "·•-_":
        s = s.replace(ch, "")
    return s


def similarity(a: str, b: str) -> float:
    a_n = normalize_name(a)
    b_n = normalize_name(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 1.0
    # 包含关系给高分
    if a_n in b_n or b_n in a_n:
        shorter = min(len(a_n), len(b_n))
        longer = max(len(a_n), len(b_n))
        return 0.85 + 0.14 * (shorter / longer)
    return SequenceMatcher(None, a_n, b_n).ratio()


# ---------------------------------------------------------------------------
# 速率限制
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, min_interval: float):
        self._interval = max(0.0, float(min_interval))
        self._last = 0.0

    def wait(self):
        if self._interval <= 0:
            return
        elapsed = time.time() - self._last
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last = time.time()


# ---------------------------------------------------------------------------
# 候选结果
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    podcast_id: str
    url: str
    title: str
    score: float


# ---------------------------------------------------------------------------
# App API（可选，需 token）
# ---------------------------------------------------------------------------

class XiaoyuzhouAuthError(Exception):
    pass


def _get_token(token_data: Dict, key_variants: List[str]) -> str:
    for k in key_variants:
        v = token_data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def load_token_file(path: str) -> Dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_token_file(path: str, data: Dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _app_headers(token_data: Dict) -> Dict[str, str]:
    access_token = _get_token(token_data, ["access_token", "x-jike-access-token", "xJikeAccessToken"])
    dev = token_data.get("device") or {}
    ver = str(dev.get("app_version") or "2.57.1")
    build = str(dev.get("app_buildno") or "1576")
    os_v = str(dev.get("os_version") or "17.4.1")
    return {
        "Host": "api.xiaoyuzhoufm.com",
        "User-Agent": f"Xiaoyuzhou/{ver} (build:{build}; iOS {os_v})",
        "App-Version": ver,
        "App-BuildNo": build,
        "OS": "ios",
        "OS-Version": os_v,
        "Market": "AppStore",
        "BundleID": "app.podcast.cosmos",
        "x-jike-access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "zh-Hans-CN;q=1.0",
        "Timezone": "Asia/Shanghai",
        "Local-Time": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _app_refresh_tokens(session: requests.Session, token_data: Dict, timeout: int) -> Dict:
    access = _get_token(token_data, ["access_token", "x-jike-access-token"])
    refresh = _get_token(token_data, ["refresh_token", "x-jike-refresh-token"])
    if not access or not refresh:
        raise XiaoyuzhouAuthError("missing tokens")
    headers = _app_headers(token_data)
    headers["x-jike-refresh-token"] = refresh
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
    r = session.post("https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh", headers=headers, timeout=timeout)
    if r.status_code == 401:
        raise XiaoyuzhouAuthError("unauthorized")
    r.raise_for_status()
    updated = dict(token_data)
    new_access = r.headers.get("x-jike-access-token")
    new_refresh = r.headers.get("x-jike-refresh-token")
    if new_access:
        updated["access_token"] = new_access
    if new_refresh:
        updated["refresh_token"] = new_refresh
    updated["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return updated


def app_search(
    session: requests.Session,
    keyword: str,
    token_data: Dict,
    token_file: str,
    timeout: int,
    limit: int = 20,
) -> List[Candidate]:
    """调用小宇宙 App API 搜索，自动刷新 token。"""
    access = _get_token(token_data, ["access_token", "x-jike-access-token"])
    if not access:
        return []

    def _do(td: Dict) -> List[Dict]:
        r = session.post(
            "https://api.xiaoyuzhoufm.com/v1/search/create",
            json={"limit": str(limit), "type": "ALL", "keyword": keyword,
                  "sourcePageName": "4", "currentPageName": "4"},
            headers=_app_headers(td),
            timeout=timeout,
        )
        if r.status_code == 401:
            raise XiaoyuzhouAuthError("unauthorized")
        r.raise_for_status()
        data = r.json() if r.content else {}
        items = (data.get("data") or {}).get("data") or []
        return items if isinstance(items, list) else []

    try:
        items = _do(token_data)
    except XiaoyuzhouAuthError as e:
        if "unauthorized" not in str(e):
            return []
        try:
            new_td = _app_refresh_tokens(session, token_data, timeout)
            token_data.clear()
            token_data.update(new_td)
            if token_file:
                save_token_file(token_file, new_td)
            items = _do(token_data)
        except Exception:
            return []
    except Exception:
        return []

    candidates = []
    for it in items:
        if not isinstance(it, dict) or (it.get("type") or "").upper() != "PODCAST":
            continue
        pid = (it.get("pid") or "").strip()
        if not pid:
            continue
        title = str(it.get("title") or "")
        url = f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
        candidates.append(Candidate(pid, url, title, similarity(keyword, title)))
    return candidates


# ---------------------------------------------------------------------------
# 小宇宙网页搜索（最优先，无需 token）
# ---------------------------------------------------------------------------

def xiaoyuzhou_web_search(
    session: requests.Session,
    keyword: str,
    timeout: int,
) -> List[Candidate]:
    """直接搜索小宇宙网页，从 __NEXT_DATA__ 提取搜索结果。"""
    url = f"https://www.xiaoyuzhoufm.com/search?q={quote(keyword)}&type=podcast"
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except Exception:
        return []

    # 方案 1：从 __NEXT_DATA__ 提取
    candidates = _parse_next_data_search(r.text, keyword)
    if candidates:
        return candidates

    # 方案 2：从 HTML 中提取播客 URL，再访问标题
    found_ids = re.findall(r"xiaoyuzhoufm\.com/podcast/([a-f0-9]{24})", r.text, re.I)
    seen = set()
    out = []
    for pid in found_ids:
        pid = pid.lower()
        if pid in seen:
            continue
        seen.add(pid)
        u = f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
        out.append(Candidate(pid, u, "", 0.0))
    return out


def _parse_next_data_search(html: str, keyword: str) -> List[Candidate]:
    """从小宇宙页面的 __NEXT_DATA__ JSON 中提取播客搜索结果。"""
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    # 遍历 pageProps 找播客列表
    podcasts = _dig_podcasts(data)
    candidates = []
    seen = set()
    for p in podcasts:
        pid = (p.get("pid") or p.get("id") or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        title = str(p.get("title") or p.get("name") or "")
        url = f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
        candidates.append(Candidate(pid, url, title, similarity(keyword, title)))
    return candidates


def _dig_podcasts(obj, depth: int = 0) -> List[Dict]:
    """递归从 JSON 中找播客对象列表。"""
    if depth > 8:
        return []
    if isinstance(obj, list):
        out = []
        for item in obj:
            if isinstance(item, dict) and ("pid" in item or ("title" in item and "subscriptionCount" in item)):
                out.append(item)
            else:
                out.extend(_dig_podcasts(item, depth + 1))
        return out
    if isinstance(obj, dict):
        out = []
        for v in obj.values():
            out.extend(_dig_podcasts(v, depth + 1))
        return out
    return []


# ---------------------------------------------------------------------------
# 搜索引擎（兜底）
# ---------------------------------------------------------------------------

def _search_engine_urls(session: requests.Session, query: str, timeout: int) -> Tuple[List[str], str]:
    """依次尝试各搜索引擎，返回 (url列表, 来源名)。"""

    def _extract_ids(text: str) -> List[str]:
        found = re.findall(r"xiaoyuzhoufm\.com/podcast/([a-f0-9]{24})", text, re.I)
        seen, out = set(), []
        for pid in found:
            pid = pid.lower()
            if pid not in seen:
                seen.add(pid)
                out.append(f"https://www.xiaoyuzhoufm.com/podcast/{pid}")
        return out

    def _sogou() -> List[str]:
        r = session.get(
            "https://www.sogou.com/web?query=" + quote(f"{query} 小宇宙 播客"),
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                     "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        r.raise_for_status()
        if "验证码" in r.text:
            return []
        return _extract_ids(r.text)

    def _bing() -> List[str]:
        r = session.get(
            "https://www.bing.com/search?q=" + quote(f"site:xiaoyuzhoufm.com/podcast {query}"),
            timeout=timeout,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        ids = []
        for a in soup.select("li.b_algo h2 a"):
            m = PODCAST_URL_RE.search(a.get("href") or "")
            if m:
                ids.append(f"https://www.xiaoyuzhoufm.com/podcast/{m.group(1)}")
        return ids

    def _ddg() -> List[str]:
        r = session.get(
            "https://duckduckgo.com/html/?q=" + quote(f"site:xiaoyuzhoufm.com/podcast {query}"),
            timeout=timeout,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        ids = []
        for a in soup.select("a.result__a, a.result-link"):
            m = PODCAST_URL_RE.search(a.get("href") or "")
            if m:
                ids.append(f"https://www.xiaoyuzhoufm.com/podcast/{m.group(1)}")
        return ids

    for fn, name in [(_sogou, "sogou"), (_bing, "bing"), (_ddg, "ddg")]:
        try:
            urls = fn()
            if urls:
                return urls, name
        except Exception:
            continue
    return [], ""


def _fetch_title(session: requests.Session, url: str, timeout: int) -> str:
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        # 优先 __NEXT_DATA__
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', r.text, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                props = data.get("props", {}).get("pageProps", {})
                podcast = props.get("podcast") or {}
                title = podcast.get("title") or podcast.get("name") or ""
                if title:
                    return str(title)
            except Exception:
                pass
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------

def load_cache(path: str) -> Dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(path: str, cache: Dict):
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _cache_key(line: str) -> str:
    n = normalize_name(line)
    return hashlib.sha1(n.encode("utf-8")).hexdigest() if n else ""


# ---------------------------------------------------------------------------
# 核心解析逻辑
# ---------------------------------------------------------------------------

def resolve_one(
    session: requests.Session,
    limiter: RateLimiter,
    line: str,
    max_candidates: int,
    min_score: float,
    min_gap: float,
    timeout: int,
    cache: Dict,
    refresh: bool,
    token_data: Dict,
    token_file: str,
    prefer_api: bool,
) -> Dict:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return {"input": raw, "status": "skipped"}

    key = _cache_key(raw)
    if not refresh and key and key in cache:
        return {**cache[key], "from_cache": True, "input": raw}

    # 1) 直接是 URL
    m = PODCAST_URL_RE.search(raw)
    if m:
        pid = m.group(1)
        url = f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
        limiter.wait()
        title = _fetch_title(session, url, timeout)
        result = _make_result(raw, "selected", pid, url, title, 1.0,
                              [Candidate(pid, url, title, 1.0)], "url")
        if key:
            cache[key] = result
        return result

    # 2) 搜索
    candidates: List[Candidate] = []
    source = ""

    def _try_web() -> Tuple[List[Candidate], str]:
        limiter.wait()
        cs = xiaoyuzhou_web_search(session, raw, timeout)
        return cs, "web" if cs else ""

    def _try_api() -> Tuple[List[Candidate], str]:
        if not token_data:
            return [], ""
        limiter.wait()
        cs = app_search(session, raw, token_data, token_file, timeout)
        return cs, "api" if cs else ""

    def _try_engines() -> Tuple[List[Candidate], str]:
        limiter.wait()
        urls, src = _search_engine_urls(session, raw, timeout)
        if not urls:
            return [], ""
        cs = []
        for u in urls[:max_candidates * 2]:
            m2 = PODCAST_URL_RE.search(u)
            if not m2:
                continue
            pid = m2.group(1)
            limiter.wait()
            title = _fetch_title(session, u, timeout)
            cs.append(Candidate(pid, u, title, similarity(raw, title) if title else 0.0))
        return cs, src if cs else ""

    if prefer_api:
        order = [_try_api, _try_web, _try_engines]
    else:
        order = [_try_web, _try_api, _try_engines]

    for fn in order:
        cs, src = fn()
        if cs:
            candidates = cs
            source = src
            break

    candidates.sort(key=lambda c: c.score, reverse=True)
    top = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None

    status = "not_found"
    selected = None
    if top:
        if top.score >= min_score:
            gap_ok = second is None or (top.score - second.score) >= min_gap
            status = "selected" if gap_ok else "ambiguous"
            if status == "selected":
                selected = top
        else:
            status = "ambiguous" if candidates else "not_found"

    result = _make_result(
        raw, status,
        selected.podcast_id if selected else "",
        selected.url if selected else "",
        selected.title if selected else "",
        selected.score if selected else 0.0,
        candidates[:max_candidates],
        source,
    )
    if key:
        cache[key] = result
    return result


def _make_result(
    raw: str, status: str, pid: str, url: str, title: str, score: float,
    candidates: List[Candidate], source: str,
) -> Dict:
    return {
        "input": raw,
        "status": status,
        "podcast_id": pid,
        "selected_url": url,
        "selected_title": title,
        "score": round(score, 4),
        "source": source,
        "candidates": [
            {"podcast_id": c.podcast_id, "url": c.url, "title": c.title, "score": round(c.score, 4)}
            for c in candidates
        ],
        "from_cache": False,
        "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# 批量解析 + 并发
# ---------------------------------------------------------------------------

def resolve_batch(
    lines: List[str],
    session: requests.Session,
    limiter: RateLimiter,
    cache: Dict,
    max_candidates: int,
    min_score: float,
    min_gap: float,
    timeout: int,
    refresh: bool,
    token_data: Dict,
    token_file: str,
    prefer_api: bool,
    workers: int,
) -> List[Dict]:
    results = [None] * len(lines)

    def _work(idx: int, line: str) -> Tuple[int, Dict]:
        time.sleep(random.uniform(0, 0.3))
        r = resolve_one(
            session=session, limiter=limiter, line=line,
            max_candidates=max_candidates, min_score=min_score, min_gap=min_gap,
            timeout=timeout, cache=cache, refresh=refresh,
            token_data=token_data, token_file=token_file, prefer_api=prefer_api,
        )
        return idx, r

    if workers <= 1:
        for i, line in enumerate(lines):
            _, r = _work(i, line)
            results[i] = r
            _log_result(r)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_work, i, line): i for i, line in enumerate(lines)}
            for f in as_completed(futures):
                try:
                    idx, r = f.result()
                    results[idx] = r
                    _log_result(r)
                except Exception as e:
                    idx = futures[f]
                    results[idx] = {"input": lines[idx].strip(), "status": "error", "error": str(e)}
                    logger.error(f"failed: {lines[idx].strip()} -> {e}")

    return results


def _log_result(r: Dict):
    status = r.get("status")
    name = r.get("input", "")
    if status == "selected":
        src = r.get("source", "")
        cached = " [缓存]" if r.get("from_cache") else ""
        logger.info(f"✓ {name} -> {r.get('podcast_id')} 《{r.get('selected_title')}》 [{src}]{cached}")
    elif status == "ambiguous":
        logger.warning(f"? {name} — 模糊匹配，候选数={len(r.get('candidates', []))}")
    elif status == "not_found":
        logger.warning(f"✗ {name} — 未找到")
    elif status == "skipped":
        pass
    else:
        logger.error(f"! {name} — {r.get('error', status)}")


# ---------------------------------------------------------------------------
# 写出结果
# ---------------------------------------------------------------------------

def write_outputs(results: List[Dict], output_json: str, output_csv: Optional[str]):
    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"结果已写入 {output_json}")

    if not output_csv:
        return
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["input", "status", "podcast_id", "selected_title", "selected_url", "score", "source", "from_cache"])
        for r in results:
            writer.writerow([
                r.get("input", ""), r.get("status", ""), r.get("podcast_id", ""),
                r.get("selected_title", ""), r.get("selected_url", ""),
                r.get("score", ""), r.get("source", ""), r.get("from_cache", False),
            ])
    logger.info(f"CSV 已写入 {output_csv}")


def update_config_with_results(config_path: str, results: List[Dict], overwrite: bool) -> int:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    podcasts = config.get("podcasts", [])
    by_name = {normalize_name(p.get("name", "")): p for p in podcasts if isinstance(p, dict)}

    updated = 0
    for r in results:
        if r.get("status") != "selected":
            continue
        pid = (r.get("podcast_id") or "").strip()
        key = normalize_name(r.get("input", ""))
        if not pid or not key:
            continue
        p = by_name.get(key)
        if not p:
            continue
        existing = (p.get("podcast_id") or "").strip()
        if existing and not overwrite:
            continue
        if existing == pid:
            continue
        p["podcast_id"] = pid
        updated += 1

    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, config_path)
    return updated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="解析小宇宙播客名称 -> podcast_id",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="输入文件，每行一个播客名称或 URL")
    parser.add_argument("--output", default="", help="输出 JSON 路径（默认 data/podcast_id_map_YYYY-MM-DD.json）")
    parser.add_argument("--output-csv", default="", help="额外输出 CSV 路径（可选）")
    parser.add_argument("--update-config", default="", help="解析完成后更新此 config.json 中的 podcast_id")
    parser.add_argument("--overwrite", action="store_true", help="覆盖 config.json 中已有的 podcast_id")
    parser.add_argument("--dry-run", action="store_true", help="不实际写入 config.json")

    parser.add_argument("--min-score", type=float, default=0.86, help="最低匹配得分阈值")
    parser.add_argument("--min-gap", type=float, default=0.05, help="第一候选与第二候选的最小得分差")
    parser.add_argument("--max-candidates", type=int, default=5, help="最多保留候选数")
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时（秒）")
    parser.add_argument("--request-delay", type=float, default=1.5, help="请求间最小间隔（秒）")
    parser.add_argument("--workers", type=int, default=1, help="并发线程数（建议 ≤3，过大易被限流）")
    parser.add_argument("--cache", default="data/podcast_id_resolver_cache.json", help="缓存文件路径")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存，重新解析所有输入")

    parser.add_argument("--token-file", default="", help="小宇宙 App token 文件（JSON），启用后使用 App API 搜索")
    parser.add_argument("--prefer-api", action="store_true", help="优先使用 App API 搜索（而非网页搜索）")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    today = datetime.now().strftime("%Y-%m-%d")
    output_json = args.output or f"data/podcast_id_map_{today}.json"

    cache = load_cache(args.cache)
    token_data = load_token_file(args.token_file) if args.token_file else {}

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    limiter = RateLimiter(args.request_delay)

    with open(args.input, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    logger.info(f"共 {len(lines)} 行输入，workers={args.workers}")
    results = resolve_batch(
        lines=lines,
        session=session,
        limiter=limiter,
        cache=cache,
        max_candidates=args.max_candidates,
        min_score=args.min_score,
        min_gap=args.min_gap,
        timeout=args.timeout,
        refresh=args.refresh,
        token_data=token_data,
        token_file=args.token_file,
        prefer_api=args.prefer_api,
        workers=args.workers,
    )

    write_outputs(results, output_json, args.output_csv or None)
    save_cache(args.cache, cache)

    selected = sum(1 for r in results if r.get("status") == "selected")
    ambiguous = sum(1 for r in results if r.get("status") == "ambiguous")
    not_found = sum(1 for r in results if r.get("status") == "not_found")
    logger.info(f"完成：选中 {selected} / 模糊 {ambiguous} / 未找到 {not_found} / 共 {len(results)}")

    if args.update_config and not args.dry_run:
        n = update_config_with_results(args.update_config, results, overwrite=args.overwrite)
        logger.info(f"已更新 {n} 个 podcast_id 到 {args.update_config}")


if __name__ == "__main__":
    main()
