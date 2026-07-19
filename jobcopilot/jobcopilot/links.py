"""Build pre-filtered LinkedIn job-search URLs from the profile.

This is a pure URL builder — it constructs the same search links you'd get by
typing filters into LinkedIn's own jobs search. It never logs in, scrapes, or
automates anything: you click a link and browse in your own browser.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

_JOBS_SEARCH = "https://www.linkedin.com/jobs/search/"

# LinkedIn "date posted" filter (f_TPR), seconds.
DATE_POSTED = {
    "24h": "r86400",
    "week": "r604800",
    "month": "r2592000",
    "any": "",
}

# LinkedIn "experience level" filter (f_E).
_SENIORITY_TO_FE = {
    "internship": "1",
    "entry": "2",
    "associate": "3",
    "mid": "4",          # LinkedIn groups mid + senior as "Mid-Senior level"
    "senior": "4",
    "lead": "5",
    "director": "5",
    "executive": "6",
}

# LinkedIn "workplace type" filter (f_WT): 1 on-site, 2 remote, 3 hybrid.
_WORKPLACE = {"onsite": "1", "remote": "2", "hybrid": "3"}


def _fe(seniority: str) -> str:
    return _SENIORITY_TO_FE.get((seniority or "").strip().lower(), "")


def _looks_remote(location: str) -> bool:
    return "remote" in (location or "").lower()


def build_links(
    profile: dict[str, Any],
    date_posted: str = "week",
    remote_only: bool = False,
    max_links: int = 24,
) -> list[dict[str, str]]:
    """Return [{label, url}] — one pre-filtered LinkedIn search per title × location.

    Falls back to the keyword list when no target titles are set.
    """
    titles = profile.get("target_titles") or []
    if not titles:
        kws = profile.get("keywords") or []
        titles = [" ".join(kws[:4])] if kws else []
    if not titles:
        return []

    locations = profile.get("locations") or [""]
    f_e = _fe(profile.get("seniority", ""))
    f_tpr = DATE_POSTED.get(date_posted, DATE_POSTED["week"])

    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for title in titles:
        for location in locations:
            params: dict[str, str] = {"keywords": title, "sortBy": "DD"}

            remote = remote_only or _looks_remote(location)
            if remote:
                params["f_WT"] = _WORKPLACE["remote"]
                # For remote roles LinkedIn keys off a country/region, so drop the
                # "Remote" token from the location string but keep any region name.
                cleaned = _strip_remote(location)
                if cleaned:
                    params["location"] = cleaned
            elif location:
                params["location"] = location

            if f_e:
                params["f_E"] = f_e
            if f_tpr:
                params["f_TPR"] = f_tpr

            url = f"{_JOBS_SEARCH}?{urlencode(params)}"
            if url in seen:
                continue
            seen.add(url)

            loc_label = params.get("location", "")
            label_bits = [title]
            if remote:
                label_bits.append("remote")
            if loc_label:
                label_bits.append(loc_label)
            links.append({"label": " · ".join(label_bits), "url": url})
            if len(links) >= max_links:
                return links
    return links


def _strip_remote(location: str) -> str:
    """Turn 'Remote (EU)' / 'Remote - Germany' into 'EU' / 'Germany'."""
    s = (location or "").strip()
    for token in ("remote", "(", ")", "-", "—", ":"):
        s = s.replace(token, " ").replace(token.upper(), " ").replace(token.title(), " ")
    return " ".join(s.split()).strip()
