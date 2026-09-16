#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_bilibili.py
================
从 B 站同步《王者万象棋》教学视频到 data.json 的 videos 数组。
纯标准库实现（urllib / json / hashlib / time / re），无需 pip 安装任何依赖。

两种运行模式
------------
A. 关键词发现（默认，免费 CI 可用，已验证）：
   搜索「王者万象棋 打法/阵容教学/攻略」等关键词取最新视频，自动收录全网相关打法视频。
   配置的「优先作者」(BILI_PREFERRED) 会被打上 featured 标记，页面上置顶/标推荐。

B. 严格锁定 UP 主（需登录 Cookie，可选）：
   配置 BILI_MIDS(UID 列表) + BILI_COOKIE(登录 Cookie)，调用空间投稿接口
   拉取指定 UP 主的全部最新投稿，100% 只收这些人。
   注意：B 站空间接口在无登录环境下返回 -403/-352，必须带 Cookie 才能用。

机制要点
--------
  * 搜索接口必须带 WBI 签名(w_rid)，否则被风控拦截。
  * 相关性过滤用「万象棋专属信号词」，而非死卡"万象棋"三字，避免误杀
    （如「转生海月胡牌」「从零成为顶尖棋手」这类不含"万象棋"三字的万象棋视频）。
  * 失败保护：一次都没抓到时保留原 videos，不清空。

字段对齐 index.html（id/url/level/tag/author/title/desc/featured）：
  id= bvid   url= https://www.bilibili.com/video/<bvid>
  level= 入门/进阶/冲分   tag= 版本更新/新棋手/阵容/打法/通用
  author=UP主名   title=清洗后标题   desc=简介前50字   featured=是否优先作者

环境变量
  BILI_KEYWORDS   逗号分隔搜索词（发现模式），默认见下方
  BILI_PREFERRED  逗号分隔的优先作者名（发现模式中标 featured），如 厌小修,西君,...
  BILI_MIDS       逗号分隔 UP 主 UID（严格锁定模式，需 BILI_COOKIE）
  BILI_COOKIE     B 站登录 Cookie（严格锁定模式才需要）
  BILI_MAX        最多保留视频数，默认 30
  DATA_FILE       data.json 路径，默认脚本同级 ../data.json
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import time
import hashlib
import re
import os
import sys

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 57, 22, 25, 54,
    21, 56, 59, 6, 60, 36, 30, 4, 51, 62, 11, 34, 44, 52, 20, 63,
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 万象棋专属信号词：命中其一才算万象棋内容（避免混入普通王者荣耀）
RELEVANT = ["万象棋", "棋手", "阵容码", "钻石狂潮", "转生", "胡牌", "羁绊", "养成", "运营"]

# 专题标签：按优先级匹配，命中第一个即归类
TAG_RULES = [
    ("版本更新", ["版本", "更新", "调整", "平衡", "削弱", "增强", "改动", "补丁", "热修", "环境"]),
    ("新棋手",   ["新棋手", "棋手", "技能", "英雄", "介绍", "上线", "机制"]),
    ("阵容",     ["阵容", "体系", "搭配", "羁绊", "阵容码", "码"]),
    ("打法",     ["打法", "运营", "思路", "教学", "上分", "冲分", "玩法", "怎么玩", "养成", "公式"]),
]
LEVEL_RULES = [
    ("入门", ["入门", "新手", "教学", "胎教", "零基础", "怎么玩", "基础", "保姆", "科普"]),
    ("冲分", ["冲分", "上分", "T0", "排行", "高分", "999", "登顶", "宗师", "稳上", "最强", "爆炸"]),
]


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)


def fetch_json(url: str, params: dict, referer: str, cookie: str = None) -> dict:
    query = urllib.parse.urlencode(params)
    headers = {"User-Agent": UA, "Referer": referer}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url + "?" + query, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def get_wbi_mixin() -> str:
    d = fetch_json(
        "https://api.bilibili.com/x/web-interface/nav",
        {}, "https://www.bilibili.com",
    )
    img = d["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
    sub = d["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
    return get_mixin_key(img, sub)


def wbi_sign(params: dict, mixin: str) -> dict:
    params = dict(sorted(params.items()))
    q = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    return params


def search_videos(keyword: str, mixin: str, ps: int = 30) -> list:
    params = {
        "search_type": "video", "keyword": keyword,
        "order": "pubdate", "ps": str(ps), "pn": "1",
        "wts": str(int(time.time())),
    }
    params = wbi_sign(params, mixin)
    d = fetch_json(
        "https://api.bilibili.com/x/web-interface/wbi/search/type",
        params, "https://search.bilibili.com",
    )
    if d.get("code") != 0:
        print(f"[warn] 关键词「{keyword}」返回 code={d.get('code')} msg={d.get('message')}")
        return []
    return [it for it in (d.get("data", {}).get("result") or []) if it.get("bvid")]


def space_videos(mid: str, mixin: str, cookie: str, pages: int = 3) -> list:
    out = []
    for pn in range(1, pages + 1):
        params = {
            "mid": str(mid), "ps": "30", "pn": str(pn),
            "order": "pubdate", "wts": str(int(time.time())),
        }
        params = wbi_sign(params, mixin)
        try:
            d = fetch_json(
                "https://api.bilibili.com/x/space/wbi/arc/search",
                params, f"https://space.bilibili.com/{mid}", cookie,
            )
        except Exception as e:
            print(f"[warn] 空间接口 mid={mid} 第{pn}页失败: {e}")
            break
        vlist = ((d.get("data") or {}).get("list") or {}).get("vlist") or []
        if not vlist:
            break
        out.extend(vlist)
    return out


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def classify(rules: list, text: str, default: str) -> str:
    for label, keys in rules:
        if any(k in text for k in keys):
            return label
    return default


def is_relevant(title: str, desc: str) -> bool:
    text = title + " " + desc
    return any(k in text for k in RELEVANT)


def make_video(bvid: str, title: str, desc: str, author: str, featured: bool) -> dict:
    return {
        "id": bvid,
        "url": f"https://www.bilibili.com/video/{bvid}",
        "level": classify(LEVEL_RULES, title, "进阶"),
        "tag": classify(TAG_RULES, title + " " + desc, "通用"),
        "author": author or "B站UP主",
        "title": title,
        "desc": desc[:50],
        "featured": featured,
    }


def collect_search(keywords: list, mixin: str, preferred: list) -> list:
    seen = {}
    for kw in keywords:
        try:
            items = search_videos(kw, mixin)
        except Exception as e:
            print(f"[warn] 关键词「{kw}」请求失败: {e}")
            continue
        for it in items:
            bv = it.get("bvid")
            if not bv or bv in seen:
                continue
            title = clean_html(it.get("title", ""))
            desc = clean_html(it.get("description", ""))
            if not is_relevant(title, desc):
                continue
            author = it.get("author", "B站UP主")
            feat = any(
                p and (p == author or any(author.startswith(p + sep)
                        for sep in ("-", "_", "·", " ", "—", "：")))
                for p in preferred
            )
            seen[bv] = make_video(bv, title, desc, author, feat)
        print(f"[sync] 关键词「{kw}」累计 {len(seen)} 条")
    return list(seen.values())


def collect_space_locked(mids: list, mixin: str, cookie: str) -> list:
    seen = set()
    videos = []
    for mid in mids:
        items = space_videos(mid, mixin, cookie)
        n = 0
        for it in items:
            bv = it.get("bvid")
            if not bv or bv in seen:
                continue
            title = clean_html(it.get("title", ""))
            desc = clean_html(it.get("description", ""))
            if not is_relevant(title, desc):
                continue
            seen.add(bv)
            videos.append(make_video(bv, title, desc, it.get("author", "B站UP主"), True))
            n += 1
        print(f"[sync] 锁定 UP 主 mid={mid} 收录 {n} 条")
    return videos


def main():
    preferred = [n.strip() for n in os.environ.get("BILI_PREFERRED", "").split(",") if n.strip()]
    mids = [m.strip() for m in os.environ.get("BILI_MIDS", "").split(",") if m.strip()]
    cookie = os.environ.get("BILI_COOKIE", "").strip()

    max_videos = int(os.environ.get("BILI_MAX", "30"))
    here = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.abspath(os.environ.get("DATA_FILE", os.path.join(here, "..", "data.json")))

    if mids and cookie:
        print(f"[sync] 严格锁定模式：UID={mids}（带登录 Cookie）")
    elif mids and not cookie:
        print("[warn] 配置了 BILI_MIDS 但未提供 BILI_COOKIE，空间接口将失败。"
              "回退到关键词发现模式。")
    else:
        print(f"[sync] 关键词发现模式，优先作者={preferred or '无'}")

    print(f"[sync] 目标文件: {data_file}")

    try:
        mixin = get_wbi_mixin()
    except Exception as e:
        print(f"[error] 获取 WBI 密钥失败: {e}")
        sys.exit(1)

    if mids and cookie:
        videos = collect_space_locked(mids, mixin, cookie)
    else:
        keywords = os.environ.get(
            "BILI_KEYWORDS",
            "王者万象棋 打法,王者万象棋 阵容教学,王者万象棋 攻略,"
            "万象棋 上分,万象棋 阵容,万象棋 教学,万象棋 新版本",
        ).split(",")
        keywords = [k.strip() for k in keywords if k.strip()]
        videos = collect_search(keywords, mixin, preferred)

    # 优先作者置顶
    videos.sort(key=lambda v: (not v.get("featured"), v["tag"]))
    videos = videos[:max_videos]

    if not videos:
        print("[sync] 未抓到任何相关视频，保留 data.json 原有 videos，不覆盖。")
        return

    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data["videos"] = videos

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    from collections import Counter
    print("[sync] 专题分布:", dict(Counter(v["tag"] for v in videos)))
    print("[sync] 优先作者视频:", sum(1 for v in videos if v.get("featured")))
    print(f"[sync] 完成，写入 {len(videos)} 条视频到 {data_file}")


if __name__ == "__main__":
    main()
