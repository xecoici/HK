# -*- coding: utf-8 -*-
import re
import json
import time
import base64
import ssl
import urllib.request
import urllib.error
from urllib.parse import quote, urlparse, urlencode, unquote


class Spider:
    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend
        host = ""
        try:
            if isinstance(extend, dict):
                host = extend.get("host") or extend.get("video_host") or ""
            elif isinstance(extend, str) and extend.strip().startswith("{"):
                host = json.loads(extend).get("host", "")
        except Exception:
            host = ""
        self.site = (host or "https://lk21.de").rstrip("/")
        self.UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.site_headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": self.site + "/",
        }
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
        except Exception:
            pass
        self._img_cache = {}
        self._pc_cache = {}
        self.server_priority = ["P2P", "TURBOVIP", "CAST", "HYDRAX", "VIDSRC", "FILEMOON", "STREAMTAPE", "DOODSTREAM", "MIXDROP", "UPSTREAM", "MP4UPLOAD", "VIDGUARD"]

    def getName(self):
        return "LK21"

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return True

    def _http(self, url, data=None, headers=None, timeout=15):
        h = dict(self.site_headers)
        if headers:
            h.update(headers)
        body = None
        if data is not None:
            body = data if isinstance(data, bytes) else urlencode(data).encode("utf-8")
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        req = urllib.request.Request(url, data=body, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), dict(r.headers), r.url
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.read(), dict(e.headers), url
            except Exception:
                return e.code, b"", {}, url
        except Exception:
            return 0, b"", {}, url

    def _get_text(self, url, headers=None, timeout=15):
        st, raw, hh, final = self._http(url, headers=headers, timeout=timeout)
        if st != 200 or not raw:
            return ""
        for enc in ("utf-8", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", "ignore")

    def fetch(self, url, headers=None, timeout=15, max_retries=2):
        for i in range(max_retries):
            if i:
                time.sleep(1.5 * i)
            t = self._get_text(url, headers=headers, timeout=timeout)
            if t:
                return t
        return ""

    def _abs_url(self, src):
        if not src:
            return ""
        if src.startswith("http"):
            return src
        if src.startswith("//"):
            return "https:" + src
        if src.startswith("/"):
            return self.site + src
        return self.site + "/" + src

    def _striptags(self, s):
        s = re.sub(r"<[^>]+>", "", s or "")
        for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
            s = s.replace(a, b)
        return re.sub(r"\s+", " ", s).strip()

    def _norm_id(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            return self._norm_id(ids[0]) if ids else ""
        s = str(ids).strip()
        if s.startswith("["):
            try:
                arr = json.loads(s)
                if isinstance(arr, list) and arr:
                    return self._norm_id(arr[0])
            except Exception:
                pass
        return unquote(s)

    def _clean_title(self, title):
        if not title:
            return ""
        pats = [r"\([^)]*\)", r"\[[^\]]*\]", r"Nonton\s+", r"Streaming\s+", r"Download\s+",
                r"Sub\s+Indo", r"Subtitle\s+Indonesia", r"LK21", r"Layarkaca21", r"\d{3,4}p",
                r"\bHD\b", r"\bFHD\b", r"BluRay", r"WEB-DL", r"WEBRip", r"\s+di\s+Lk21.*$",
                r"\s+di\s*$", r"^Film\s+", r"^Movie\s+"]
        c = title
        for p in pats:
            c = re.sub(p, "", c, flags=re.I)
        c = re.sub(r"\s+", " ", c).strip()
        return c if c else title.strip()

    def _proxy_img(self, url):
        if not url:
            return ""
        try:
            f = getattr(self, "getProxyUrl", None)
            if not f:
                return url
            b64 = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii")
            pb = f()
            sep = "&" if "?" in pb else "?"
            return pb + sep + "m=img&u=" + b64
        except Exception:
            return url

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                param = {}
        if not isinstance(param, dict) or param.get("m") != "img":
            return [404, "text/plain", b"", {}]
        u = (param.get("u") or "").strip()
        if not u:
            return [404, "text/plain", b"", {}]
        try:
            raw = base64.urlsafe_b64decode(u + "=" * (-len(u) % 4)).decode("utf-8")
        except Exception:
            return [404, "text/plain", b"", {}]
        if raw in self._img_cache:
            return self._img_cache[raw]
        st, body, hh, _ = self._http(raw, headers={"Referer": "https://poster.assetsy.de/", "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}, timeout=20)
        if st != 200 or not body:
            return [404, "text/plain", b"", {}]
        ct = (hh.get("Content-Type") or "image/jpeg").split(";")[0].strip() or "image/jpeg"
        res = [200, ct, body, {}]
        if len(self._img_cache) < 50:
            self._img_cache[raw] = res
        return res

    def homeContent(self, filter=None):
        return {"class": [
            {"type_id": "latest", "type_name": "Post Terbaru"},
            {"type_id": "populer", "type_name": "Terpopuler"},
            {"type_id": "rating", "type_name": "Rating"},
            {"type_id": "release", "type_name": "Urut Tahun"},
            {"type_id": "most-commented", "type_name": "Komen Terbanyak"},
            {"type_id": "nontondrama", "type_name": "Series"},
            {"type_id": "genre-action", "type_name": "Action"},
            {"type_id": "genre-comedy", "type_name": "Comedy"},
            {"type_id": "genre-drama", "type_name": "Drama"},
            {"type_id": "genre-horror", "type_name": "Horror"},
            {"type_id": "genre-romance", "type_name": "Romance"},
            {"type_id": "genre-thriller", "type_name": "Thriller"},
            {"type_id": "genre-animation", "type_name": "Animation"},
            {"type_id": "genre-scifi", "type_name": "Sci-Fi"},
            {"type_id": "country-usa", "type_name": "Amerika"},
            {"type_id": "country-uk", "type_name": "Inggris"},
            {"type_id": "country-japan", "type_name": "Jepang"},
            {"type_id": "country-south-korea", "type_name": "Korea"},
            {"type_id": "country-china", "type_name": "Cina"},
            {"type_id": "country-india", "type_name": "India"},
            {"type_id": "year-2026", "type_name": "2026"},
            {"type_id": "year-2025", "type_name": "2025"},
            {"type_id": "year-2024", "type_name": "2024"},
        ], "filters": {}}
    def _parse_card(self, b):
        m = re.search(r'<a\b[^>]*href="([^"]+)"', b, re.I)
        if not m:
            return None
        href = m.group(1).strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            return None
        hl = href.lower()
        if any(p in hl for p in ["/genre/", "/country/", "/year/", "/page/", "/populer", "/rating",
                                 "/latest", "/release", "/faq", "/dmca", "/privacy", "/search",
                                 "/tag/", "/actor/", "/director/"]):
            return None
        url = self._abs_url(href)
        title = ""
        m2 = re.search(r"<h3\b[^>]*>(.*?)</h3>", b, re.I | re.S)
        if m2:
            title = self._striptags(m2.group(1))
        if not title:
            m2 = re.search(r'class="[^"]*poster-title[^"]*"[^>]*>(.*?)</', b, re.I | re.S)
            if m2:
                title = self._striptags(m2.group(1))
        img = ""
        alt = ""
        for im in re.finditer(r"<img\b[^>]*>", b, re.I):
            tag = im.group(0)
            for attr in ("data-src", "data-lazy-src", "data-original", "src"):
                mm = re.search(attr + r'\s*=\s*"([^"]+)"', tag, re.I)
                if mm and mm.group(1).strip():
                    img = mm.group(1).split(",")[0].strip().split(" ")[0]
                    break
            if not img:
                mm = re.search(r'data-srcset\s*=\s*"([^"]+)"', tag, re.I)
                if mm:
                    img = mm.group(1).split(",")[0].strip().split(" ")[0]
            ma = re.search(r'alt\s*=\s*"([^"]*)"', tag, re.I)
            if ma:
                alt = ma.group(1).strip()
            if img or alt:
                break
        if not title:
            title = alt
        if not title:
            return None
        year = ""
        my = re.search(r"(19\d{2}|20\d{2})", b)
        if my:
            year = my.group(1)
        if img.startswith("//"):
            img = "https:" + img
        elif img.startswith("/"):
            img = self.site + img
        remarks = ""
        mq = re.search(r'class="[^"]*(?:quality|label|badge)[^"]*"[^>]*>([^<]{1,12})<', b, re.I)
        if mq:
            remarks = mq.group(1).strip()
        return {"vod_id": url,
                "vod_name": self._clean_title(title)[:100] or "Unknown",
                "vod_pic": self._proxy_img(img),
                "vod_year": year,
                "vod_remarks": remarks[:20] or "HD"}

    def _parse_cards(self, html):
        items = []
        seen = set()
        blocks = re.findall(r"<article\b[^>]*>(.*?)</article>", html, re.I | re.S)
        if not blocks:
            blocks = re.findall(r'<div\b[^>]*class="[^"]*(?:ml-item|movie-item|post)[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.I | re.S)
        for b in blocks[:60]:
            try:
                v = self._parse_card(b)
            except Exception:
                continue
            if not v or v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            items.append(v)
        return items

    def _pagecount(self, html, pg):
        try:
            nums = [int(x) for x in re.findall(r"/page/(\d+)/", html)]
            if nums:
                return max(nums)
        except Exception:
            pass
        return pg

    def homeVideoContent(self):
        try:
            html = self.fetch(self.site + "/")
            return {"list": self._parse_cards(html)[:40]}
        except Exception:
            return {"list": []}

    def _get_category_url(self, tid, pg):
        pg = int(pg) if pg else 1
        if tid == "latest":
            base = "/latest/"
        elif tid == "rating":
            base = "/rating/"
        elif tid == "release":
            base = "/release/"
        elif tid == "populer":
            base = "/populer/"
        elif tid == "most-commented":
            base = "/most-commented/"
        elif tid == "nontondrama":
            base = "/nontondrama/"
        elif tid.startswith("genre-"):
            base = "/genre/" + tid[6:] + "/"
        elif tid.startswith("country-"):
            base = "/country/" + tid[8:] + "/"
        elif tid.startswith("year-"):
            base = "/year/" + tid[5:] + "/"
        else:
            return self.site + "/search/?s=" + quote(tid)
        if pg > 1:
            return self.site + base + "page/" + str(pg) + "/"
        return self.site + base

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg) if pg else 1
            html = self.fetch(self._get_category_url(tid, pg))
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 40, "total": 0}
            items = self._parse_cards(html)
            pc = self._pagecount(html, pg)
            return {"list": items, "page": pg, "pagecount": pc, "limit": 40, "total": len(items)}
        except Exception:
            return {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 40, "total": 0}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if pg else 1
            enc = quote(key or "")
            url = self.site + "/search/?s=" + enc if pg == 1 else self.site + "/search/page/" + str(pg) + "/?s=" + enc
            html = self.fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1}
            items = self._parse_cards(html)[:40]
            pc = self._pagecount(html, pg)
            return {"list": items, "page": pg, "pagecount": max(pc, pg), "limit": 40, "total": len(items)}
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1}

    def _detect_servers(self, html):
        groups = {}

        def _add(server, url):
            server = (server or "").strip().upper()
            url = (url or "").strip()
            if not server or not url or url.startswith("#") or url.lower().startswith("javascript:"):
                return
            url = self._abs_url(url)
            groups.setdefault(server, [])
            if url not in groups[server]:
                groups[server].append(url)

        for mt in re.finditer(r"<a\b[^>]*>", html, re.I):
            tag = mt.group(0)
            ms = re.search(r'data-server\s*=\s*"([^"]*)"', tag, re.I)
            if ms:
                mu = re.search(r'data-url\s*=\s*"([^"]*)"', tag, re.I) or re.search(r'href\s*=\s*"([^"]*)"', tag, re.I)
                if mu:
                    _add(ms.group(1), mu.group(1))
        for mt in re.finditer(r"<option\b[^>]*>(.*?)</option>", html, re.I | re.S):
            tag = mt.group(0)
            mu = re.search(r'value\s*=\s*"([^"]+)"', tag, re.I)
            if mu and mu.group(1).strip().lower().startswith("http"):
                ms = re.search(r'data-server\s*=\s*"([^"]*)"', tag, re.I)
                name = ms.group(1) if ms else re.sub(r"(?i)GANTI PLAYER", "", self._striptags(mt.group(1))).strip()
                _add(name or "SERVER", mu.group(1))
        for ms in re.finditer(r'<iframe\b[^>]*src="([^"]+)"', html, re.I):
            src = ms.group(1).strip()
            mg = re.search(r"/iframe\d*/([a-zA-Z0-9_-]+)/", src)
            _add(mg.group(1) if mg else "IFRAME", src)
        for mt in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.I | re.S):
            for a, host in re.findall(r'(https?://[^\s"\']+/iframe\d*/([a-zA-Z0-9_-]+)/[^\s"\']+)', mt.group(1)):
                _add(host, a)
        return groups

    def _order_servers(self, d):
        out = []
        used = set()
        for p in self.server_priority:
            if p in d:
                out.append(p)
                used.add(p)
        for k in d:
            if k not in used:
                out.append(k)
        return out

    def detailContent(self, ids):
        try:
            path = self._norm_id(ids)
            if not path:
                return {"list": []}
            full_url = self._abs_url(path)
            html = self.fetch(full_url)
            if not html:
                return {"list": []}
            title = pic = year = rating = ""
            m = re.search(r'<script[^>]*id="watch-history-data"[^>]*>(.*?)</script>', html, re.I | re.S)
            if m:
                try:
                    d = json.loads(m.group(1).strip())
                    title = d.get("title", "") or ""
                    pic = d.get("poster", "") or ""
                    year = str(d.get("year", "") or "")
                    rating = str(d.get("rating", "") or "")
                except Exception:
                    pass
            if not title:
                h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
                if h1:
                    title = re.sub(r"\s*\(\d{4}\)\s*$", "", self._striptags(h1.group(1)))
            if not pic:
                og = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, re.I)
                if og:
                    pic = og.group(1)
            if not year:
                h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
                if h1:
                    my = re.search(r"\((\d{4})\)", h1.group(1))
                    if my:
                        year = my.group(1)
            sinopsis = ""
            sy = re.search(r'class="[^"]*synopsis[^"]*"[^>]*>(.*?)</div>', html, re.I | re.S)
            if sy:
                sinopsis = self._striptags(sy.group(1))[:800]
            if not sinopsis:
                md = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html, re.I)
                if md:
                    sinopsis = md.group(1)[:800]
            groups = self._detect_servers(html)
            ordered = self._order_servers(groups)
            pfs = []
            pus = []
            for name in ordered:
                urls = groups[name]
                eps = []
                for i, u in enumerate(urls):
                    label = name + " #" + str(i + 1) if len(urls) > 1 else name
                    eps.append(label + "$" + u)
                pfs.append(name)
                pus.append("#".join(eps))
            if not pfs:
                pfs.append("DIRECT")
                pus.append("Play$" + full_url)
            remarks = str(len(pfs)) + " Server"
            if rating:
                remarks = rating + " | " + remarks
            return {"list": [{
                "vod_id": path,
                "vod_name": (self._clean_title(title) or title or "Unknown")[:150],
                "vod_pic": self._proxy_img(self._abs_url(pic)),
                "vod_year": year,
                "vod_area": "",
                "vod_remarks": remarks,
                "vod_content": sinopsis,
                "vod_play_from": "$$$".join(pfs),
                "vod_play_url": "$$$".join(pus),
            }]}
        except Exception:
            return {"list": []}
    def _resolve_videonode(self, url):
        m = re.search(r"/iframe\d*/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)", url)
        if not m:
            return None
        host, vid = m.group(1), m.group(2)
        pu = urlparse(url)
        base = pu.scheme + "://" + pu.netloc
        st, raw, hh, _ = self._http(base + "/api.php", data={"host": host, "id": vid}, headers={"Referer": url}, timeout=15)
        if st != 200 or not raw:
            return None
        try:
            emb = json.loads(raw.decode("utf-8", "ignore")).get("embedUrl", "")
        except Exception:
            return None
        if not emb:
            return None
        if emb.startswith("//"):
            emb = "https:" + emb
        if not emb.startswith("http"):
            return None
        slug = emb.rstrip("/").split("/")[-1].split("?")[0]
        eu = urlparse(emb)
        ebase = eu.scheme + "://" + eu.netloc
        ref = {"User-Agent": self.UA, "Referer": ebase + "/"}
        st2, raw2, hh2, _ = self._http(ebase + "/verify/" + quote(slug), headers={"Referer": emb}, timeout=15)
        if st2 == 200 and raw2:
            try:
                d2 = json.loads(raw2.decode("utf-8", "ignore"))
            except Exception:
                d2 = {}
            fu = d2.get("fileUrl", "") or ""
            if d2.get("status") == "success" and ".m3u8" in fu.lower() and fu.startswith("http"):
                return (fu, ref)
        page = self._get_text(emb, headers={"Referer": url}, timeout=15)
        if page:
            for pat in (r'"fileUrl"\s*:\s*"([^"]+)"', r'"file"\s*:\s*"([^"]+)"', r"(https?://[^\s\"'<>\\\\]+\.m3u8[^\s\"'<>\\\\]*)"):
                mm = re.search(pat, page)
                if mm:
                    fu = mm.group(1).replace("\\/", "/")
                    if fu.startswith("//"):
                        fu = "https:" + fu
                    if fu.startswith("http"):
                        return (fu, ref)
        return None

    def _pick_best(self, urls):
        def score(u):
            s = 0
            ul = u.lower()
            if ".m3u8" in ul:
                s += 100
            if ".mp4" in ul:
                s += 50
            if "master" in ul:
                s += 20
            if "playlist" in ul:
                s += 15
            if "index" in ul:
                s += 10
            if any(x in ul for x in ["1080", "720", "hd"]):
                s += 10
            if any(x in ul for x in ["ads", "advert", "banner", "popup", "trailer", "sample"]):
                s -= 50
            return s
        return max(urls, key=score)

    def _resolve_to_direct(self, url, server_name="", depth=0):
        if not url or not url.startswith("http"):
            return None
        if self.isVideoFormat(url):
            pu = urlparse(url)
            return (url, {"User-Agent": self.UA, "Referer": pu.scheme + "://" + pu.netloc + "/"})
        if re.search(r"/iframe\d*/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+", url):
            return self._resolve_videonode(url)
        if depth > 2:
            return None
        html = self._get_text(url, timeout=12)
        if not html:
            return None
        found = []
        for pat in (r'"((?:https?:)?//[^"]*?\.m3u8[^"]*?)"', r"'(https?://[^']*?\.m3u8[^']*?)'",
                    r'"((?:https?:)?//[^"]*?\.mp4[^"]*?)"', r"(https?://[^\s\"'<>\\\\]+\.m3u8[^\s\"'<>\\\\]*)",
                    r"(https?://[^\s\"'<>\\\\]+\.mp4[^\s\"'<>\\\\]*)"):
            for mm in re.findall(pat, html, re.I):
                u = mm.replace("\\/", "/")
                if u.startswith("//"):
                    u = "https:" + u
                if u.startswith("http") and u not in found:
                    found.append(u)
        if found:
            pu = urlparse(url)
            return (self._pick_best(found), {"User-Agent": self.UA, "Referer": url, "Origin": pu.scheme + "://" + pu.netloc})
        for ms in re.finditer(r'<iframe\b[^>]*src="([^"]+)"', html, re.I):
            src = ms.group(1).strip()
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                pu = urlparse(url)
                src = pu.scheme + "://" + pu.netloc + src
            if src.startswith("http"):
                r = self._resolve_to_direct(src, server_name, depth + 1)
                if r:
                    return r
        for dec in re.findall(r'atob\(\s*"([A-Za-z0-9+/=]+)"\s*\)', html):
            try:
                d = base64.b64decode(dec + "=" * (-len(dec) % 4)).decode("utf-8", "ignore")
            except Exception:
                continue
            for mm in re.findall(r"(https?://[^\s\"']+\.(?:m3u8|mp4)[^\s\"']*)", d, re.I):
                pu = urlparse(url)
                return (mm, {"User-Agent": self.UA, "Referer": url, "Origin": pu.scheme + "://" + pu.netloc})
        return None

    def _alive(self, url, referer):
        try:
            st, raw, hh, _ = self._http(url, headers={"Referer": referer}, timeout=10)
            return st == 200 and raw[:7] == b"#EXTM3U"
        except Exception:
            return False

    def playerContent(self, flag, ids, vipFlags=None):
        try:
            raw = self._norm_id(ids)
            server_name = str(flag or "")
            url = raw
            if "$" in raw:
                server_name, url = raw.split("$", 1)
            if not url or not url.startswith("http"):
                return {"parse": 1, "url": raw}
            if self.isVideoFormat(url):
                pu = urlparse(url)
                return {"parse": 0, "url": url,
                        "header": {"User-Agent": self.UA, "Referer": pu.scheme + "://" + pu.netloc + "/"},
                        "format": "video/mp4" if ".mp4" in url.lower() else "application/x-mpegURL"}
            ck = ("pc", url)
            hit = self._pc_cache.get(ck)
            if hit and time.time() - hit[0] < 900:
                return hit[1]
            res = self._resolve_to_direct(url, server_name)
            if res:
                final_url, headers = res
                if self._alive(final_url, headers.get("Referer", self.site + "/")):
                    out = {"parse": 0, "url": final_url, "header": headers, "format": "application/x-mpegURL"}
                    self._pc_cache[ck] = (time.time(), out)
                    return out
            out = {"parse": 1, "url": url, "header": {"User-Agent": self.UA, "Referer": self.site + "/"}}
            self._pc_cache[ck] = (time.time(), out)
            return out
        except Exception:
            return {"parse": 1, "url": ""}

    def action(self, action):
        try:
            if isinstance(action, str):
                action = json.loads(action)
        except Exception:
            action = {}
        return {}

    def destroy(self):
        return None
