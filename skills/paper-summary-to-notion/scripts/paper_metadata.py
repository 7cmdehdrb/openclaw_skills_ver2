#!/usr/bin/env python3
import argparse
import json
import re
from difflib import SequenceMatcher
from urllib.parse import quote

import requests


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def crossref_search(title: str):
    url = f"https://api.crossref.org/works?query.title={quote(title)}&rows=5"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    if not items:
        return None
    scored = []
    for it in items:
        t = (it.get("title") or [""])[0]
        scored.append((sim(title, t), it))
    scored.sort(key=lambda x: x[0], reverse=True)
    score, best = scored[0]
    return score, best


def openalex_by_title(title: str):
    url = f"https://api.openalex.org/works?search={quote(title)}&per-page=5"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    items = r.json().get("results", [])
    if not items:
        return None
    scored = []
    for it in items:
        t = it.get("display_name", "")
        scored.append((sim(title, t), it))
    scored.sort(key=lambda x: x[0], reverse=True)
    score, best = scored[0]
    return score, best


def get_crossref_citations(doi: str):
    apa = None
    bib = None
    if not doi:
        return apa, bib

    enc = quote(doi, safe="")
    # APA
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{enc}/transform/application/vnd.citationstyles.csl+json",
            timeout=20,
        )
        if r.ok:
            csl = r.json()
            # compact APA-like line
            authors = []
            for a in csl.get("author", []):
                family = a.get("family", "")
                given = a.get("given", "")
                if family:
                    authors.append(f"{family}, {given[:1]}." if given else family)
            y = csl.get("issued", {}).get("date-parts", [[None]])[0][0]
            ttl = csl.get("title", "")
            cont = csl.get("container-title", "")
            doi_txt = csl.get("DOI", doi)
            apa = f"{' ; '.join(authors)} ({y}). {ttl}. {cont}. https://doi.org/{doi_txt}".strip()
    except Exception:
        pass

    # BibTeX
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{enc}/transform/application/x-bibtex",
            timeout=20,
        )
        if r.ok:
            bib = r.text.strip()
    except Exception:
        pass

    return apa, bib


def main():
    ap = argparse.ArgumentParser(description="Fetch paper metadata (year, venue, citation count, APA/BibTeX)")
    ap.add_argument("--title", required=True)
    args = ap.parse_args()

    title = args.title

    cr = crossref_search(title)
    oa = openalex_by_title(title)

    doi = None
    year = None
    venue = None
    citation_count = None
    cr_title = None
    confidence = 0.0

    if cr:
        confidence, item = cr
        doi = item.get("DOI")
        year = ((item.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        venue = ((item.get("container-title") or [None])[0])
        cr_title = ((item.get("title") or [None])[0])

    # prefer OpenAlex for citation count and fill missing fields
    if oa:
        oa_score, w = oa
        citation_count = w.get("cited_by_count")
        if not year:
            year = w.get("publication_year")
        if not venue:
            venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        if not doi:
            doi = (w.get("ids") or {}).get("doi", "").replace("https://doi.org/", "") or None
        confidence = max(confidence, oa_score)

    apa, bibtex = get_crossref_citations(doi)

    out = {
        "input_title": title,
        "matched_title": cr_title or (oa[1].get("display_name") if oa else None),
        "match_confidence": round(confidence, 3),
        "year": year,
        "journal": venue,
        "citation_count": citation_count,
        "doi": doi,
        "citation": {
            "apa": apa,
            "bibtex": bibtex,
        },
        "notes": "If confidence is low (<0.75), verify with Google Scholar manually.",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
