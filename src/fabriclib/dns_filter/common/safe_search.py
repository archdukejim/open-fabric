# Safe search (manual 1.12.2.15): the one table fabric enforces and the console names, built from the providers'
# published names. Google's search sites: google.com/supported_domains (2026-10-10).
GOOGLE_DOMAINS = """
com ad ae com.af com.ag al am co.ao com.ar as at com.au az ba com.bd be bf bg com.bh bi bj com.bn com.bo
com.br bs bt co.bw by com.bz ca cd cf cg ch ci co.ck cl cm cn com.co co.cr com.cu cv com.cy cz de dj dk dm
com.do dz com.ec ee com.eg es com.et fi com.fj fm fr ga ge gg com.gh com.gi gl gm gr com.gt gy com.hk hn hr
ht hu co.id ie co.il im co.in iq is it je com.jm jo co.jp co.ke com.kh ki kg co.kr com.kw kz la com.lb li lk
co.ls lt lu lv com.ly co.ma md me mg mk ml com.mm mn com.mt mu mv mw com.mx com.my co.mz com.na com.ng com.ni
ne nl no com.np nr nu co.nz com.om com.pa com.pe com.pg com.ph com.pk pl pn com.pr ps pt com.py com.qa ro ru
rw com.sa com.sb sc se com.sg sh si sk com.sl sn so sm sr st com.sv td tg co.th com.tj tl tm tn to com.tr tt
com.tw co.tz com.ua co.ug co.uk com.uy co.uz com.vc co.ve co.vi com.vn vu ws rs co.za co.zm co.zw cat
""".split()
# Yandex's search sites; family search is an address, not a name. xn--d1acpjx3f.xn--p1ai is яндекс.рф
YANDEX_SITES = ["yandex." + d for d in """
az by co.il com.am com.ge com.ru com.tr com de ee eu fi fr kz lt lv md net org pl ru tj tm uz
""".split()] + ["ya.ru", "xn--d1acpjx3f.xn--p1ai"]
YOUTUBE_NAMES = ["www.youtube.com", "m.youtube.com", "youtubei.googleapis.com", "youtube.googleapis.com",
                 "www.youtube-nocookie.com"]
YOUTUBE_LEVELS = {"strict": "restrict.youtube.com", "moderate": "restrictmoderate.youtube.com"}

# engine, the names rewritten, the record type and answer (YouTube's answer is chosen by its level)
ENGINES = [
    ("Google", ["www.google." + d for d in GOOGLE_DOMAINS], "CNAME", "forcesafesearch.google.com"),
    ("YouTube", YOUTUBE_NAMES, "CNAME", None),
    ("Bing", ["www.bing.com", "edgeservices.bing.com"], "CNAME", "strict.bing.com"),
    ("DuckDuckGo", ["duckduckgo.com", "www.duckduckgo.com", "start.duckduckgo.com"], "CNAME", "safe.duckduckgo.com"),
    ("Yandex", YANDEX_SITES + ["www." + s for s in YANDEX_SITES], "A", "213.180.193.56"),
    ("Pixabay", ["pixabay.com"], "CNAME", "safesearch.pixabay.com"),
    ("Ecosia", ["www.ecosia.org"], "CNAME", "strict-safe-search.ecosia.org"),
]
NOT_COVERED = ["Brave Search", "Startpage"]
# the two zones a view may load: every engine strict, or YouTube moderate and the rest strict
ZONES = {"strict": "safesearch-strict.rpz", "moderate": "safesearch-ytmoderate.rpz"}


def safe_search_records(youtube):
    """Purpose: the safe-search zone's records for one YouTube level (every other engine strict).
    Inputs:  youtube — "strict" or "moderate".
    Returns: list of (name, type, answer) — answer a name with a trailing dot, or an address.
    Fails:   KeyError for another level.
    Feeds:   dns_filter/deploy_resolver (the safesearch zones), dns_filter/filter_overview (the console's list)."""
    out = []
    for _, names, rtype, answer in ENGINES:
        target = answer or YOUTUBE_LEVELS[youtube]
        for n in names:
            out.append((n, rtype, target + "." if rtype == "CNAME" else target))
    return out


def safe_search_summary():
    """Purpose: what the console's Strict safe search switch names: each engine, how many names, what it answers.
    Inputs:  none.
    Returns: {"engines": [{"engine", "names": int, "answer": str}], "not_covered": [str], "youtube":
             {level: name}}.
    Fails:   never.
    Feeds:   dns_filter/filter_overview."""
    return {"engines": [{"engine": e, "names": len(n), "answer": a or " or ".join(YOUTUBE_LEVELS.values())}
                        for e, n, _, a in ENGINES],
            "not_covered": NOT_COVERED, "youtube": dict(YOUTUBE_LEVELS)}
