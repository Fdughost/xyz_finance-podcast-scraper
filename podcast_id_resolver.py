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
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


PODCAST_URL_RE = re.compile(r"https?://www\.xiaoyuzhoufm\.com/podcast/([a-f0-9]{24})", re.I)


class XiaoyuzhouAuthError(Exception):
    pass


def _iso_local_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_token_file(path: str) -> Dict:
    if not path:
        return {}
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("token file must be a json object")
    return data


def save_token_file(path: str, data: Dict):
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_access_token(token_data: Dict) -> str:
    if not isinstance(token_data, dict):
        return ""
    for k in ["access_token", "x-jike-access-token", "x_jike_access_token", "xJikeAccessToken"]:
        v = token_data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def get_refresh_token(token_data: Dict) -> str:
    if not isinstance(token_data, dict):
        return ""
    for k in ["refresh_token", "x-jike-refresh-token", "x_jike_refresh_token", "xJikeRefreshToken"]:
        v = token_data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def build_app_headers(access_token: str, token_data: Dict) -> Dict[str, str]:
    device = token_data.get("device") if isinstance(token_data, dict) else None
    device = device if isinstance(device, dict) else {}

    app_version = str(device.get("app_version") or device.get("App-Version") or "2.57.1")
    app_buildno = str(device.get("app_buildno") or device.get("App-BuildNo") or "1576")
    os_name = str(device.get("os") or device.get("OS") or "ios")
    os_version = str(device.get("os_version") or device.get("OS-Version") or "17.4.1")
    model = str(device.get("model") or device.get("Model") or "iPhone14,2")
    timezone = str(device.get("timezone") or device.get("Timezone") or "Asia/Shanghai")
    market = str(device.get("market") or device.get("Market") or "AppStore")
    bundle_id = str(device.get("bundle_id") or device.get("BundleID") or "app.podcast.cosmos")
    manufacturer = str(device.get("manufacturer") or device.get("Manufacturer") or "Apple")

    ua = str(device.get("user_agent") or device.get("User-Agent") or f"Xiaoyuzhou/{app_version} (build:{app_buildno}; iOS {os_version})")
    local_time = str(device.get("local_time") or device.get("Local-Time") or _iso_local_time())
    abtest_info = str(device.get("abtest_info") or device.get("abtest-info") or "{\"old_user_discovery_feed\":\"enable\"}")

    return {
        "Host": "api.xiaoyuzhoufm.com",
        "User-Agent": ua,
        "Market": market,
        "App-BuildNo": app_buildno,
        "OS": os_name,
        "x-jike-access-token": access_token,
        "Manufacturer": manufacturer,
        "BundleID": bundle_id,
        "Connection": "keep-alive",
        "abtest-info": abtest_info,
        "Accept-Language": "zh-Hant-HK;q=1.0, zh-Hans-CN;q=0.9",
        "Model": model,
        "app-permissions": "4",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "App-Version": app_version,
        "WifiConnected": "true",
        "OS-Version": os_version,
        "x-custom-xiaoyuzhou-app-dev": "",
        "Local-Time": local_time,
        "Timezone": timezone,
    }


def refresh_app_tokens(session: requests.Session, token_data: Dict, timeout: int = 20) -> Dict:
    access_token = get_access_token(token_data)
    refresh_token = get_refresh_token(token_data)
    if not access_token or not refresh_token:
        raise XiaoyuzhouAuthError("missing access_token or refresh_token")

    url = "https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh"
    headers = build_app_headers(access_token, token_data)
    headers["x-jike-refresh-token"] = refresh_token
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"

    r = session.post(url, headers=headers, timeout=timeout)
    if r.status_code == 401:
        raise XiaoyuzhouAuthError("unauthorized")
    r.raise_for_status()

    new_access = r.headers.get("x-jike-access-token") or r.headers.get("X-Jike-Access-Token")
    new_refresh = r.headers.get("x-jike-refresh-token") or r.headers.get("X-Jike-Refresh-Token")

    updated = dict(token_data) if isinstance(token_data, dict) else {}
    if new_access:
        updated["access_token"] = new_access
    if new_refresh:
        updated["refresh_token"] = new_refresh
    updated["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return updated


def app_search_podcast_candidates(
    session: requests.Session,
    keyword: str,
    token_data: Dict,
    timeout: int = 20,
    limit: int = 20,
) -> List[Dict]:
    access_token = get_access_token(token_data)
    if not access_token:
        raise XiaoyuzhouAuthError("missing access_token")

    url = "https://api.xiaoyuzhoufm.com/v1/search/create"
    headers = build_app_headers(access_token, token_data)
    payload = {
        "limit": str(int(limit)),
        "sourcePageName": "4",
        "type": "ALL",
        "currentPageName": "4",
        "keyword": keyword,
    }

    r = session.post(url, json=payload, headers=headers, timeout=timeout)
    if r.status_code == 401:
        raise XiaoyuzhouAuthError("unauthorized")
    r.raise_for_status()
    data = r.json() if r.content else {}
    d = data.get("data") if isinstance(data, dict) else None
    items = d.get("data") if isinstance(d, dict) else None
    if not isinstance(items, list):
        return []

    out: List[Dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if (it.get("type") or "").upper() != "PODCAST":
            continue
        pid = (it.get("pid") or "").strip()
        if not pid:
            continue
        title = str(it.get("title") or "")
        sub_count = it.get("subscriptionCount")
        try:
            sub_count_i = int(sub_count) if sub_count is not None else 0
        except Exception:
            sub_count_i = 0
        out.append({
            "podcast_id": pid,
            "url": f"https://www.xiaoyuzhoufm.com/podcast/{pid}",
            "title": title,
            "subscription_count": sub_count_i,
        })
    return out


def app_send_code(
    session: requests.Session,
    mobile_phone_number: str,
    area_code: str,
    token_data: Dict,
    timeout: int = 20,
):
    access_token = get_access_token(token_data)
    headers = build_app_headers(access_token or "", token_data)
    headers.pop("x-jike-access-token", None)

    url = "https://api.xiaoyuzhoufm.com/v1/auth/sendCode"
    payload = {
        "mobilePhoneNumber": mobile_phone_number,
        "areaCode": area_code or "+86",
    }
    r = session.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()


def app_login_with_sms(
    session: requests.Session,
    mobile_phone_number: str,
    verify_code: str,
    area_code: str,
    token_data: Dict,
    timeout: int = 20,
) -> Dict:
    access_token = get_access_token(token_data)
    headers = build_app_headers(access_token or "", token_data)
    headers.pop("x-jike-access-token", None)

    url = "https://api.xiaoyuzhoufm.com/v1/auth/loginOrSignUpWithSMS"
    payload = {
        "mobilePhoneNumber": mobile_phone_number,
        "verifyCode": verify_code,
        "areaCode": area_code or "+86",
    }
    r = session.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()

    new_access = r.headers.get("x-jike-access-token") or r.headers.get("X-Jike-Access-Token")
    new_refresh = r.headers.get("x-jike-refresh-token") or r.headers.get("X-Jike-Refresh-Token")
    if not new_access or not new_refresh:
        raise XiaoyuzhouAuthError("login did not return tokens in headers")

    updated = dict(token_data) if isinstance(token_data, dict) else {}
    updated["access_token"] = new_access
    updated["refresh_token"] = new_refresh
    updated["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return updated


def normalize_name(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = s.strip().lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    s = s.replace("·", "")
    s = s.replace("•", "")
    s = s.replace("-", "")
    s = s.replace("_", "")
    return s


def similarity(a: str, b: str) -> float:
    a_n = normalize_name(a)
    b_n = normalize_name(b)
    if not a_n or not b_n:
        return 0.0
    return SequenceMatcher(None, a_n, b_n).ratio()


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._last_ts = 0.0

    def wait(self):
        if self._min_interval_seconds <= 0:
            return
        now = time.time()
        elapsed = now - self._last_ts
        if elapsed < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - elapsed)
        self._last_ts = time.time()


@dataclass
class Candidate:
    podcast_id: str
    url: str
    title: str
    score: float


def extract_podcast_id_from_url(line: str) -> Optional[str]:
    if not line:
        return None
    m = PODCAST_URL_RE.search(line.strip())
    if not m:
        return None
    return m.group(1)


def fetch_podcast_title(session: requests.Session, url: str, timeout: int = 20) -> str:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def duckduckgo_search_podcast_urls(session: requests.Session, query: str, timeout: int = 20) -> List[str]:
    # Use DuckDuckGo HTML endpoint (no JS). This is best-effort.
    q = f"site:xiaoyuzhoufm.com/podcast {query}"
    url = "https://duckduckgo.com/html/?q=" + quote(q)
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    urls: List[str] = []
    for a in soup.select("a.result__a, a.result-link"):
        href = a.get("href") or ""
        m = PODCAST_URL_RE.search(href)
        if m:
            pid = m.group(1)
            urls.append(f"https://www.xiaoyuzhoufm.com/podcast/{pid}")
    # de-dup preserving order
    seen = set()
    out = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def sogou_search_podcast_urls(session: requests.Session, query: str, timeout: int = 20) -> List[str]:
    # Sogou web search tends to expose direct result URLs in HTML.
    q = f"{query} 小宇宙 播客"
    url = "https://www.sogou.com/web?query=" + quote(q)
    r = session.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.sogou.com/",
        },
    )
    r.raise_for_status()
    # Some responses may ask for verification; treat as empty.
    if "验证码" in r.text or "verify" in r.text.lower():
        return []

    found_ids = re.findall(r"https?://www\.xiaoyuzhoufm\.com/podcast/([a-f0-9]{24})", r.text, flags=re.I)
    urls: List[str] = [f"https://www.xiaoyuzhoufm.com/podcast/{pid.lower()}" for pid in found_ids]
    seen = set()
    out: List[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def so_search_podcast_urls(session: requests.Session, query: str, timeout: int = 20) -> List[str]:
    # 360 Search (so.com) often works well for Chinese queries without JS requirements.
    q = f"{query} 小宇宙 播客"
    # m.so.com 对中文搜索更稳定；但偶发“访问异常”，因此需要重试/切换 UA。
    mobile_ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    )
    desktop_ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    url_templates = [
        "https://m.so.com/s?q={q}",
        "https://www.so.com/s?q={q}",
        "https://www.so.com/s?ie=utf-8&src=home_suggest&q={q}",
    ]
    uas = [mobile_ua, desktop_ua]

    html = ""
    last_err: Optional[Exception] = None
    for attempt in range(6):
        tpl = url_templates[attempt % len(url_templates)]
        ua = uas[attempt % len(uas)]
        u = tpl.format(q=quote(q))
        try:
            r = session.get(
                u,
                timeout=timeout,
                headers={
                    "User-Agent": ua,
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://www.so.com/",
                },
            )
            r.raise_for_status()
            text = r.text
            if any(x in text for x in ["访问异常", "异常页面", "验证码", "verify"]):
                # backoff + jitter
                time.sleep((2 ** min(attempt, 3)) + random.uniform(0, 1))
                continue
            if len(text) < 10000:
                # 通常是异常/空壳页面
                time.sleep(0.5 + random.uniform(0, 0.8))
                continue
            html = text
            break
        except Exception as e:
            last_err = e
            time.sleep(0.5 + random.uniform(0, 0.8))
            continue

    if not html:
        if last_err:
            raise last_err
        return []

    # Use regex to harvest links; the page is large and structure may change.
    found_ids: List[str] = []
    found_ids.extend(re.findall(r"xiaoyuzhoufm\.com/podcast/([a-f0-9]{24})", html, flags=re.I))
    urls: List[str] = [f"https://www.xiaoyuzhoufm.com/podcast/{pid.lower()}" for pid in found_ids]
    seen = set()
    out: List[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def bing_search_podcast_urls(session: requests.Session, query: str, timeout: int = 20) -> List[str]:
    q = f"site:xiaoyuzhoufm.com/podcast {query}"
    url = "https://www.bing.com/search?q=" + quote(q)
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    urls: List[str] = []
    for a in soup.select("li.b_algo h2 a"):
        href = a.get("href") or ""
        m = PODCAST_URL_RE.search(href)
        if m:
            pid = m.group(1)
            urls.append(f"https://www.xiaoyuzhoufm.com/podcast/{pid}")
    seen = set()
    out = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


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


def cache_key(line: str) -> str:
    n = normalize_name(line)
    if not n:
        return ""
    return hashlib.sha1(n.encode("utf-8")).hexdigest()


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
    login_mode: bool,
    token_data: Dict,
    token_file_path: str,
    login_prefer_api: bool,
    login_max_results: int,
) -> Dict:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return {"input": raw, "status": "skipped"}

    key = cache_key(raw)
    if (not refresh) and key and key in cache:
        cached = cache[key]
        cached = dict(cached)
        cached["from_cache"] = True
        cached["input"] = raw
        cached.setdefault("source", "cache")
        cached.setdefault("auth_used", False)
        return cached

    # 1) URL extraction
    pid = extract_podcast_id_from_url(raw)
    if pid:
        url = f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
        title = ""
        try:
            limiter.wait()
            title = fetch_podcast_title(session, url, timeout=timeout)
        except Exception:
            title = ""
        result = {
            "input": raw,
            "status": "selected",
            "podcast_id": pid,
            "selected_url": url,
            "selected_title": title,
            "candidates": [
                {
                    "podcast_id": pid,
                    "url": url,
                    "title": title,
                    "score": 1.0,
                }
            ],
            "from_cache": False,
            "source": "url",
            "auth_used": False,
            "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if key:
            cache[key] = dict(result)
        return result

    # 2) Search via App API (optional) and public search engines
    urls: List[str] = []
    candidates: List[Candidate] = []
    source = ""
    auth_used = False

    def _try_public_search() -> Tuple[List[str], str]:
        u2: List[str] = []
        try:
            limiter.wait()
            u2 = duckduckgo_search_podcast_urls(session, raw, timeout=timeout)
            if u2:
                return u2, "ddg"
        except Exception:
            u2 = []
        try:
            limiter.wait()
            u2 = so_search_podcast_urls(session, raw, timeout=timeout)
            if u2:
                return u2, "so"
        except Exception:
            u2 = []
        try:
            limiter.wait()
            u2 = sogou_search_podcast_urls(session, raw, timeout=timeout)
            if u2:
                return u2, "sogou"
        except Exception:
            u2 = []
        try:
            limiter.wait()
            u2 = bing_search_podcast_urls(session, raw, timeout=timeout)
            if u2:
                return u2, "bing"
        except Exception:
            u2 = []
        return [], ""

    def _try_app_search() -> Tuple[List[Candidate], bool]:
        if not login_mode:
            return [], False
        if not token_data:
            return [], False

        def _do_search(td: Dict) -> List[Dict]:
            limiter.wait()
            return app_search_podcast_candidates(
                session=session,
                keyword=raw,
                token_data=td,
                timeout=timeout,
                limit=login_max_results,
            )

        hits: List[Dict] = []
        td2 = token_data
        try:
            hits = _do_search(td2)
        except XiaoyuzhouAuthError as e:
            if str(e) == "unauthorized":
                try:
                    limiter.wait()
                    td2 = refresh_app_tokens(session, td2, timeout=timeout)
                    if isinstance(token_data, dict):
                        token_data.clear()
                        token_data.update(td2)
                    if token_file_path:
                        save_token_file(token_file_path, td2)
                    hits = _do_search(td2)
                except Exception:
                    hits = []
            else:
                hits = []
        except Exception:
            hits = []

        out2: List[Candidate] = []
        for it in hits:
            if not isinstance(it, dict):
                continue
            pid3 = (it.get("podcast_id") or "").strip()
            if not pid3:
                continue
            title3 = str(it.get("title") or "")
            url3 = str(it.get("url") or f"https://www.xiaoyuzhoufm.com/podcast/{pid3}")
            score3 = similarity(raw, title3) if title3 else 0.0
            out2.append(Candidate(podcast_id=pid3, url=url3, title=title3, score=score3))

        out2.sort(key=lambda c: c.score, reverse=True)
        return out2, True

    if login_prefer_api:
        candidates, auth_used = _try_app_search()
        if candidates:
            source = "app_api"
        else:
            urls, source = _try_public_search()
    else:
        urls, source = _try_public_search()
        if not urls:
            candidates, auth_used = _try_app_search()
            if candidates:
                source = "app_api"

    if not candidates and urls:
        for u in urls[: max_candidates * 2]:
            pid2 = extract_podcast_id_from_url(u)
            if not pid2:
                continue
            title = ""
            try:
                limiter.wait()
                title = fetch_podcast_title(session, u, timeout=timeout)
            except Exception:
                title = ""
            score = similarity(raw, title) if title else 0.0
            candidates.append(Candidate(podcast_id=pid2, url=u, title=title, score=score))

    candidates.sort(key=lambda c: c.score, reverse=True)
    top = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None

    status = "not_found"
    selected: Optional[Candidate] = None
    if top and top.score >= min_score:
        gap_ok = True
        if second is not None:
            gap_ok = (top.score - second.score) >= min_gap
        if gap_ok:
            status = "selected"
            selected = top
        else:
            status = "ambiguous"
    elif candidates:
        status = "ambiguous"

    result = {
        "input": raw,
        "status": status,
        "podcast_id": selected.podcast_id if selected else "",
        "selected_url": selected.url if selected else "",
        "selected_title": selected.title if selected else "",
        "min_score": min_score,
        "min_gap": min_gap,
        "candidates": [
            {
                "podcast_id": c.podcast_id,
                "url": c.url,
                "title": c.title,
                "score": round(c.score, 4),
            }
            for c in candidates[:max_candidates]
        ],
        "from_cache": False,
        "source": source or "",
        "auth_used": bool(auth_used) if source == "app_api" else False,
        "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if key:
        cache[key] = dict(result)
    return result


def update_config_with_results(config_path: str, results: List[Dict], overwrite: bool) -> int:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    podcasts = config.get("podcasts", [])
    if not isinstance(podcasts, list):
        raise ValueError("config.json: 'podcasts' 必须是列表")

    # build lookup from normalized name
    by_name: Dict[str, Dict] = {}
    for p in podcasts:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "")
        by_name[normalize_name(name)] = p

    updated = 0
    for r in results:
        if r.get("status") != "selected":
            continue
        pid = (r.get("podcast_id") or "").strip()
        if not pid:
            continue
        key = normalize_name(r.get("input", ""))
        if not key:
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


def write_outputs(results: List[Dict], output_json: str, output_csv: Optional[str]):
    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if not output_csv:
        return
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "input",
            "status",
            "podcast_id",
            "selected_title",
            "selected_url",
            "from_cache",
            "source",
            "auth_used",
        ])
        for r in results:
            writer.writerow([
                r.get("input", ""),
                r.get("status", ""),
                r.get("podcast_id", ""),
                r.get("selected_title", ""),
                r.get("selected_url", ""),
                r.get("from_cache", False),
                r.get("source", ""),
                r.get("auth_used", False),
            ])


def main():
    parser = argparse.ArgumentParser(description="Resolve Xiaoyuzhou podcast_id from mixed name/URL list.")
    parser.add_argument("--input", default="", help="Input file: each line is a podcast name or URL")
    parser.add_argument("--output", default="", help="Output json path. Default: data/podcast_id_map_YYYY-MM-DD.json")
    parser.add_argument("--output-csv", default="", help="Optional output csv path")
    parser.add_argument("--update-config", default="", help="If set, patch this config.json with resolved ids")
    parser.add_argument("--dry-run", action="store_true", help="If set, do not update config.json")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing podcast_id in config.json")
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.86)
    parser.add_argument("--min-gap", type=float, default=0.05)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--request-delay", type=float, default=1.5)
    parser.add_argument("--cache", default="data/podcast_id_resolver_cache.json")
    parser.add_argument("--refresh", action="store_true", help="Bypass cache and re-resolve all inputs")
    parser.add_argument("--login-mode", action="store_true", help="Enable Xiaoyuzhou app API search using token file")
    parser.add_argument("--token-file", default="", help="Token json file for app API search/refresh")
    parser.add_argument("--login-prefer-api", action="store_true", help="Prefer app API search before public engines")
    parser.add_argument("--login-max-results", type=int, default=20, help="Max app API search results to consider")

    parser.add_argument("--sms-send-code", action="store_true", help="Send SMS verify code to mobile phone (may fail due to risk control)")
    parser.add_argument("--sms-login", action="store_true", help="Login with SMS verify code and save tokens to --token-file (may fail due to risk control)")
    parser.add_argument("--sms-phone", default="", help="Mobile phone number for SMS login")
    parser.add_argument("--sms-code", default="", help="Verify code received via SMS")
    parser.add_argument("--sms-area-code", default="+86", help="Area code, default +86")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    today = datetime.now().strftime("%Y-%m-%d")
    output_json = args.output or f"data/podcast_id_map_{today}.json"
    output_csv = args.output_csv or ""

    cache = load_cache(args.cache)

    token_data: Dict = {}
    if args.login_mode:
        if not args.token_file:
            raise SystemExit("--login-mode requires --token-file")
        token_data = load_token_file(args.token_file)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    limiter = RateLimiter(args.request_delay)

    if args.sms_send_code or args.sms_login:
        if not args.sms_phone:
            raise SystemExit("--sms-send-code/--sms-login requires --sms-phone")
        if not args.token_file:
            raise SystemExit("--sms-send-code/--sms-login requires --token-file")

        td = {}
        if os.path.exists(args.token_file):
            try:
                td = load_token_file(args.token_file)
            except Exception:
                td = {}

        if args.sms_send_code:
            limiter.wait()
            app_send_code(
                session=session,
                mobile_phone_number=args.sms_phone,
                area_code=args.sms_area_code,
                token_data=td,
                timeout=args.timeout,
            )
            logger.info("sms code requested")
            return

        if args.sms_login:
            if not args.sms_code:
                raise SystemExit("--sms-login requires --sms-code")
            limiter.wait()
            td2 = app_login_with_sms(
                session=session,
                mobile_phone_number=args.sms_phone,
                verify_code=args.sms_code,
                area_code=args.sms_area_code,
                token_data=td,
                timeout=args.timeout,
            )
            save_token_file(args.token_file, td2)
            logger.info("sms login ok; tokens saved")
            return

    if not args.input:
        raise SystemExit("--input is required unless using --sms-send-code/--sms-login")

    with open(args.input, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    results: List[Dict] = []
    for line in lines:
        # small jitter to avoid being too uniform
        time.sleep(random.uniform(0, 0.3))
        try:
            r = resolve_one(
                session=session,
                limiter=limiter,
                line=line,
                max_candidates=args.max_candidates,
                min_score=args.min_score,
                min_gap=args.min_gap,
                timeout=args.timeout,
                cache=cache,
                refresh=args.refresh,
                login_mode=args.login_mode,
                token_data=token_data,
                token_file_path=args.token_file,
                login_prefer_api=args.login_prefer_api,
                login_max_results=args.login_max_results,
            )
            results.append(r)
            if r.get("status") == "selected":
                logger.info(f"selected: {r.get('input')} -> {r.get('podcast_id')} ({r.get('selected_title')})")
            elif r.get("status") == "ambiguous":
                logger.warning(f"ambiguous: {r.get('input')} (candidates={len(r.get('candidates', []))})")
            elif r.get("status") == "not_found":
                logger.warning(f"not_found: {r.get('input')}")
        except Exception as e:
            logger.error(f"failed: {line} -> {e}")
            results.append({"input": line.strip(), "status": "error", "error": str(e)})

    write_outputs(results, output_json, output_csv if output_csv else None)
    save_cache(args.cache, cache)

    if args.update_config and not args.dry_run:
        updated = update_config_with_results(args.update_config, results, overwrite=args.overwrite)
        logger.info(f"config updated: {updated} podcast_id filled")

    logger.info(f"done. output: {output_json}")


if __name__ == "__main__":
    main()
