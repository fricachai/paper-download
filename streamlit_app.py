import base64
import html
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote, quote_plus

import requests
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(
    page_title="期刊文章電子檔查找系統",
    page_icon="📄",
    layout="wide",
)

DEFAULT_AUTH_USERNAMES = ["frica"]
DEFAULT_AUTH_PASSWORD = "stock2026"

API_SOURCES = [
    "OpenAlex",
    "Semantic Scholar",
    "Crossref",
    "Google Scholar (SerpAPI)",
    "Scopus (Elsevier API)",
    "ScienceDirect (Elsevier API)",
    "Web of Science (API)",
    "Springer Nature",
    "PubMed",
    "Europe PMC",
    "ERIC",
    "DOAJ",
    "arXiv",
    "CORE",
    "DataCite",
]

DEFAULT_PUBLIC_SOURCES = [
    "OpenAlex",
    "Semantic Scholar",
    "Crossref",
    "PubMed",
    "Europe PMC",
    "ERIC",
    "DOAJ",
    "arXiv",
    "DataCite",
]


def get_auth_config() -> tuple[list[str], str]:
    try:
        usernames = list(st.secrets.get("AUTH_USERNAMES", DEFAULT_AUTH_USERNAMES))
        password = str(st.secrets.get("AUTH_PASSWORD", DEFAULT_AUTH_PASSWORD))
    except Exception:
        usernames = DEFAULT_AUTH_USERNAMES
        password = DEFAULT_AUTH_PASSWORD
    return usernames, password


def login_styles() -> None:
    st.markdown(
        """
        <style>
          .stApp {
            background:
              radial-gradient(circle at top left, rgba(54, 104, 190, 0.14), transparent 26%),
              radial-gradient(circle at bottom right, rgba(255, 152, 17, 0.08), transparent 24%),
              #f7f8fb;
          }
          .login-shell {
            display: grid;
            min-height: 72vh;
            place-items: center;
          }
          .login-frame {
            border-radius: 22px;
            padding: 2px;
            width: min(100%, 420px);
            background: linear-gradient(115deg, #ff63c8, #ffbe72, #7ce1ff, #b47cff, #ff63c8);
            box-shadow:
              0 24px 60px rgba(0, 0, 0, 0.18),
              0 0 18px rgba(124, 225, 255, 0.18);
          }
          .login-panel {
            border-radius: 20px;
            padding: 28px;
            background: linear-gradient(180deg, rgba(17, 20, 27, 0.98), rgba(11, 13, 18, 0.99));
            color: #f5f6fa;
          }
          .login-panel h1 {
            margin: 0 0 8px;
            text-align: center;
            font-size: 28px;
          }
          .login-panel p {
            margin: 0;
            color: #a9b2c2;
            text-align: center;
          }
          div[data-testid="stForm"] {
            border: 0;
            box-shadow: none;
            background: transparent;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login_gate() -> bool:
    if st.session_state.get("authenticated"):
        return True

    login_styles()
    st.markdown(
        """
        <div class="login-shell">
          <div class="login-frame">
            <div class="login-panel">
              <h1>登入期刊文章系統</h1>
              <p>請輸入授權帳號與密碼後繼續。</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    usernames, password = get_auth_config()
    with st.form("login-form"):
        username = st.text_input("帳號", autocomplete="username")
        entered_password = st.text_input("密碼", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("登入")

    if submitted:
        if username.strip() in usernames and entered_password == password:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("帳號或密碼錯誤。")

    st.stop()


def render_logout_button() -> None:
    if st.sidebar.button("登出"):
        st.session_state.pop("authenticated", None)
        st.rerun()


def clean_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:180] or "Unknown_Title"


def normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "")).strip()


def article_key(article: dict) -> str:
    doi = normalize_doi(article.get("doi", "")).lower()
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(article.get('title', '')).casefold()}"


def normalize_article(
    *,
    source: str,
    title: str,
    year: int | str | None = 0,
    doi: str = "",
    journal: str = "",
    cited_by_count: int = 0,
    relevance_score: float = 0,
    authors: str = "",
    pdf_url: str = "",
    landing_page_url: str = "",
    is_oa: bool = False,
) -> dict:
    year_value = int(year) if str(year or "").isdigit() else 0
    doi = normalize_doi(doi)
    return {
        "title": normalize_title(title) or "Untitled",
        "year": year_value,
        "doi": doi,
        "journal": journal or "",
        "cited_by_count": int(cited_by_count or 0),
        "relevance_score": float(relevance_score or 0),
        "authors": authors or "",
        "pdf_url": pdf_url or "",
        "landing_page_url": landing_page_url or (f"https://doi.org/{doi}" if doi else ""),
        "is_oa": bool(is_oa or pdf_url),
        "sources": [source],
    }


def merge_articles(article_lists: list[list[dict]], limit: int) -> list[dict]:
    merged: dict[str, dict] = {}
    for articles in article_lists:
        for article in articles:
            key = article_key(article)
            if not key or key == "title:":
                continue
            if key not in merged:
                merged[key] = article
                continue

            existing = merged[key]
            existing["sources"] = sorted(set(existing["sources"] + article["sources"]))
            existing["cited_by_count"] = max(existing["cited_by_count"], article["cited_by_count"])
            existing["relevance_score"] = max(existing["relevance_score"], article["relevance_score"])
            for field in ("doi", "journal", "authors", "pdf_url", "landing_page_url"):
                if not existing.get(field) and article.get(field):
                    existing[field] = article[field]
            existing["is_oa"] = existing["is_oa"] or article["is_oa"]

    results = list(merged.values())
    results.sort(key=lambda item: (-item["relevance_score"], -int(item["year"] or 0), -item["cited_by_count"]))
    return results[:limit]


def format_openalex_authors(authorships: list[dict]) -> str:
    names = []
    for authorship in authorships[:5]:
        author = authorship.get("author") or {}
        if author.get("display_name"):
            names.append(author["display_name"])
    if len(authorships) > 5:
        names.append("et al.")
    return "; ".join(names)


def request_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 20) -> dict:
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def from_year_filter(recent_years: int | None) -> int | None:
    if not recent_years:
        return None
    return datetime.now().year - recent_years + 1


def search_openalex(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    filters = ["type:article"]
    from_year = from_year_filter(recent_years)
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    data = request_json(
        "https://api.openalex.org/works",
        {
            "search": keyword,
            "filter": ",".join(filters),
            "per-page": min(max(limit * 2, 25), 200),
        },
        timeout=25,
    )
    articles = []
    for work in data.get("results", []):
        doi_url = work.get("doi") or ""
        best_oa = work.get("best_oa_location") or {}
        primary = work.get("primary_location") or {}
        source = (primary.get("source") or {}).get("display_name", "")
        articles.append(
            normalize_article(
                source="OpenAlex",
                title=work.get("title"),
                year=work.get("publication_year"),
                doi=doi_url,
                journal=source,
                cited_by_count=work.get("cited_by_count") or 0,
                relevance_score=work.get("relevance_score") or 0,
                authors=format_openalex_authors(work.get("authorships") or []),
                pdf_url=best_oa.get("pdf_url") or "",
                landing_page_url=best_oa.get("landing_page_url") or doi_url,
                is_oa=bool(work.get("open_access", {}).get("is_oa")),
            )
        )
    return articles


def search_semantic_scholar(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    fields = "title,year,authors,journal,citationCount,externalIds,openAccessPdf,url,isOpenAccess"
    data = request_json(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        {"query": keyword, "limit": min(limit, 100), "fields": fields},
        timeout=25,
    )
    from_year = from_year_filter(recent_years)
    articles = []
    for item in data.get("data", []):
        year = item.get("year") or 0
        if from_year and year and year < from_year:
            continue
        external = item.get("externalIds") or {}
        journal = (item.get("journal") or {}).get("name", "")
        pdf = item.get("openAccessPdf") or {}
        authors = "; ".join(author.get("name", "") for author in (item.get("authors") or [])[:5] if author.get("name"))
        articles.append(
            normalize_article(
                source="Semantic Scholar",
                title=item.get("title"),
                year=year,
                doi=external.get("DOI", ""),
                journal=journal,
                cited_by_count=item.get("citationCount") or 0,
                relevance_score=100,
                authors=authors,
                pdf_url=pdf.get("url", ""),
                landing_page_url=item.get("url", ""),
                is_oa=bool(item.get("isOpenAccess")),
            )
        )
    return articles


def search_crossref(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    filters = ["type:journal-article"]
    from_year = from_year_filter(recent_years)
    if from_year:
        filters.append(f"from-pub-date:{from_year}-01-01")
    data = request_json(
        "https://api.crossref.org/works",
        {"query.bibliographic": keyword, "filter": ",".join(filters), "rows": min(limit, 100), "sort": "relevance"},
        timeout=25,
    )
    articles = []
    for item in data.get("message", {}).get("items", []):
        year = extract_crossref_year(item)
        authors = "; ".join(format_crossref_author(author) for author in (item.get("author") or [])[:5])
        pdf_url = ""
        for link in item.get("link", []) or []:
            if "pdf" in (link.get("content-type", "") + link.get("URL", "")).lower():
                pdf_url = link.get("URL", "")
                break
        articles.append(
            normalize_article(
                source="Crossref",
                title=(item.get("title") or ["Untitled"])[0],
                year=year,
                doi=item.get("DOI", ""),
                journal=(item.get("container-title") or [""])[0],
                cited_by_count=item.get("is-referenced-by-count") or 0,
                relevance_score=item.get("score") or 0,
                authors=authors,
                pdf_url=pdf_url,
                landing_page_url=item.get("URL", ""),
                is_oa=bool(pdf_url),
            )
        )
    return articles


def extract_crossref_year(item: dict) -> int:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        date_parts = item.get(key, {}).get("date-parts")
        if date_parts and date_parts[0]:
            return int(date_parts[0][0])
    return 0


def format_crossref_author(author: dict) -> str:
    return f"{author.get('given', '')} {author.get('family', '')}".strip()


def search_pubmed(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    from_year = from_year_filter(recent_years)
    term = f"{keyword} journal article"
    if from_year:
        term += f" AND {from_year}:3000[pdat]"
    search_data = request_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "pubmed", "term": term, "retmode": "json", "retmax": min(limit, 100)},
        timeout=25,
    )
    ids = search_data.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summary_data = request_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        {"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        timeout=25,
    )
    result = summary_data.get("result", {})
    articles = []
    for pmid in ids:
        item = result.get(pmid, {})
        articleids = item.get("articleids") or []
        doi = next((x.get("value", "") for x in articleids if x.get("idtype") == "doi"), "")
        authors = "; ".join(author.get("name", "") for author in (item.get("authors") or [])[:5] if author.get("name"))
        pubdate = item.get("pubdate", "")
        year = int(pubdate[:4]) if pubdate[:4].isdigit() else 0
        articles.append(
            normalize_article(
                source="PubMed",
                title=item.get("title"),
                year=year,
                doi=doi,
                journal=item.get("fulljournalname", ""),
                cited_by_count=0,
                relevance_score=80,
                authors=authors,
                landing_page_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
        )
    return articles


def search_eric(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    params = {"search": keyword, "format": "json", "rows": min(limit, 100)}
    from_year = from_year_filter(recent_years)
    if from_year:
        params["publicationdateyear"] = f"{from_year}-3000"
    data = request_json("https://api.ies.ed.gov/eric/", params, timeout=25)
    docs = data.get("response", {}).get("docs", []) or data.get("docs", [])
    articles = []
    for item in docs:
        year = item.get("publicationdateyear") or item.get("year") or 0
        authors = item.get("author") or item.get("authors") or []
        if isinstance(authors, list):
            authors = "; ".join(str(author) for author in authors[:5])
        articles.append(
            normalize_article(
                source="ERIC",
                title=item.get("title"),
                year=year,
                doi=item.get("doi", ""),
                journal=item.get("source", ""),
                cited_by_count=0,
                relevance_score=70,
                authors=str(authors),
                pdf_url=item.get("pdfurl", "") or item.get("fulltexturl", ""),
                landing_page_url=item.get("url", "") or item.get("eric_url", ""),
                is_oa=bool(item.get("pdfurl") or item.get("fulltexturl")),
            )
        )
    return articles


def search_doaj(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    data = request_json(f"https://doaj.org/api/search/articles/{quote(keyword)}", {"pageSize": min(limit, 100)}, timeout=25)
    from_year = from_year_filter(recent_years)
    articles = []
    for result in data.get("results", []):
        bibjson = result.get("bibjson", {})
        year = bibjson.get("year") or 0
        if from_year and year and int(year) < from_year:
            continue
        identifiers = bibjson.get("identifier") or []
        doi = next((item.get("id", "") for item in identifiers if item.get("type") == "doi"), "")
        links = bibjson.get("link") or []
        pdf_url = next((item.get("url", "") for item in links if item.get("type") == "fulltext"), "")
        authors = "; ".join(author.get("name", "") for author in (bibjson.get("author") or [])[:5] if author.get("name"))
        journal = (bibjson.get("journal") or {}).get("title", "")
        articles.append(
            normalize_article(
                source="DOAJ",
                title=bibjson.get("title"),
                year=year,
                doi=doi,
                journal=journal,
                cited_by_count=0,
                relevance_score=65,
                authors=authors,
                pdf_url=pdf_url,
                landing_page_url=pdf_url,
                is_oa=True,
            )
        )
    return articles


def search_arxiv(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": f"all:{keyword}", "start": 0, "max_results": min(limit, 50), "sortBy": "relevance"},
        timeout=25,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    from_year = from_year_filter(recent_years)
    articles = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", default="", namespaces=ns)
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year = int(published[:4]) if published[:4].isdigit() else 0
        if from_year and year and year < from_year:
            continue
        authors = "; ".join(author.findtext("atom:name", default="", namespaces=ns) for author in entry.findall("atom:author", ns)[:5])
        arxiv_id = entry.findtext("atom:id", default="", namespaces=ns)
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
        articles.append(
            normalize_article(
                source="arXiv",
                title=title,
                year=year,
                journal="arXiv",
                relevance_score=60,
                authors=authors,
                pdf_url=pdf_url,
                landing_page_url=arxiv_id,
                is_oa=bool(pdf_url),
            )
        )
    return articles


def get_core_api_key() -> str:
    try:
        return str(st.secrets.get("CORE_API_KEY", ""))
    except Exception:
        return os.getenv("CORE_API_KEY", "")


def get_secret_or_env(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, ""))


def require_key(name: str, source: str) -> str:
    value = get_secret_or_env(name)
    if not value:
        raise RuntimeError(f"{source} 需要設定 {name}")
    return value


def search_google_scholar_serpapi(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    api_key = require_key("SERPAPI_KEY", "Google Scholar (SerpAPI)")
    params = {
        "engine": "google_scholar",
        "q": keyword,
        "api_key": api_key,
        "num": min(limit, 20),
    }
    data = request_json("https://serpapi.com/search.json", params, timeout=25)
    from_year = from_year_filter(recent_years)
    articles = []
    for item in data.get("organic_results", []):
        publication = item.get("publication_info") or {}
        summary = publication.get("summary", "")
        year_match = re.search(r"\b(19|20)\d{2}\b", summary)
        year = int(year_match.group(0)) if year_match else 0
        if from_year and year and year < from_year:
            continue
        resources = item.get("resources") or []
        pdf_url = next((resource.get("link", "") for resource in resources if "pdf" in (resource.get("file_format", "") + resource.get("link", "")).lower()), "")
        cited_by = ((item.get("inline_links") or {}).get("cited_by") or {}).get("total", 0)
        articles.append(
            normalize_article(
                source="Google Scholar",
                title=item.get("title"),
                year=year,
                cited_by_count=cited_by,
                relevance_score=95,
                authors=summary,
                pdf_url=pdf_url,
                landing_page_url=item.get("link", ""),
                is_oa=bool(pdf_url),
            )
        )
    return articles


def search_scopus(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    api_key = require_key("ELSEVIER_API_KEY", "Scopus (Elsevier API)")
    query = f'TITLE-ABS-KEY("{keyword}")'
    from_year = from_year_filter(recent_years)
    if from_year:
        query += f" AND PUBYEAR > {from_year - 1}"
    data = request_json(
        "https://api.elsevier.com/content/search/scopus",
        {"query": query, "count": min(limit, 25), "sort": "relevancy"},
        headers={"X-ELS-APIKey": api_key, "Accept": "application/json"},
        timeout=25,
    )
    articles = []
    for item in data.get("search-results", {}).get("entry", []):
        doi = item.get("prism:doi", "")
        year = (item.get("prism:coverDate", "") or "")[:4]
        links = item.get("link") or []
        landing = next((link.get("@href", "") for link in links if link.get("@ref") == "scopus"), "")
        articles.append(
            normalize_article(
                source="Scopus",
                title=item.get("dc:title"),
                year=year,
                doi=doi,
                journal=item.get("prism:publicationName", ""),
                cited_by_count=item.get("citedby-count") or 0,
                relevance_score=90,
                authors=item.get("dc:creator", ""),
                landing_page_url=landing or (f"https://doi.org/{doi}" if doi else ""),
            )
        )
    return articles


def search_sciencedirect(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    api_key = require_key("ELSEVIER_API_KEY", "ScienceDirect (Elsevier API)")
    query = keyword
    from_year = from_year_filter(recent_years)
    if from_year:
        query += f" AND pub-date > {from_year - 1}"
    data = request_json(
        "https://api.elsevier.com/content/search/sciencedirect",
        {"query": query, "count": min(limit, 25), "sort": "relevance"},
        headers={"X-ELS-APIKey": api_key, "Accept": "application/json"},
        timeout=25,
    )
    articles = []
    for item in data.get("search-results", {}).get("entry", []):
        doi = item.get("prism:doi", "")
        year = (item.get("prism:coverDate", "") or "")[:4]
        links = item.get("link") or []
        landing = next((link.get("@href", "") for link in links if link.get("@href")), "")
        articles.append(
            normalize_article(
                source="ScienceDirect",
                title=item.get("dc:title"),
                year=year,
                doi=doi,
                journal=item.get("prism:publicationName", ""),
                relevance_score=88,
                authors=item.get("dc:creator", ""),
                landing_page_url=landing or (f"https://doi.org/{doi}" if doi else ""),
            )
        )
    return articles


def search_web_of_science(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    api_key = require_key("WOS_API_KEY", "Web of Science (API)")
    query = f'TS="{keyword}"'
    data = request_json(
        "https://api.clarivate.com/apis/wos-starter/v1/documents",
        {"q": query, "limit": min(limit, 50), "page": 1},
        headers={"X-ApiKey": api_key, "Accept": "application/json"},
        timeout=25,
    )
    from_year = from_year_filter(recent_years)
    records = data.get("hits") or data.get("documents") or []
    articles = []
    for item in records:
        year = item.get("source", {}).get("publishYear") or item.get("year") or 0
        if from_year and year and int(year) < from_year:
            continue
        identifiers = item.get("identifiers") or {}
        doi = identifiers.get("doi", "") if isinstance(identifiers, dict) else ""
        title = item.get("title") or (item.get("names", {}) or {}).get("title", "")
        source = item.get("source") or {}
        articles.append(
            normalize_article(
                source="Web of Science",
                title=title,
                year=year,
                doi=doi,
                journal=source.get("sourceTitle", "") if isinstance(source, dict) else "",
                cited_by_count=item.get("citations", [{}])[0].get("count", 0) if isinstance(item.get("citations"), list) and item.get("citations") else 0,
                relevance_score=92,
                landing_page_url=f"https://doi.org/{doi}" if doi else "",
            )
        )
    return articles


def search_springer(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    api_key = require_key("SPRINGER_API_KEY", "Springer Nature")
    query = f"keyword:{keyword}"
    from_year = from_year_filter(recent_years)
    if from_year:
        query += f" year:{from_year}-3000"
    data = request_json(
        "https://api.springernature.com/meta/v2/json",
        {"q": query, "p": min(limit, 100), "api_key": api_key},
        timeout=25,
    )
    articles = []
    for item in data.get("records", []):
        doi = item.get("doi", "")
        pdf_url = ""
        landing = ""
        for url_info in item.get("url", []) or []:
            if url_info.get("format") == "pdf":
                pdf_url = url_info.get("value", "")
            if not landing and url_info.get("value"):
                landing = url_info.get("value", "")
        articles.append(
            normalize_article(
                source="Springer Nature",
                title=item.get("title"),
                year=item.get("publicationDate", "")[:4],
                doi=doi,
                journal=item.get("publicationName", ""),
                relevance_score=84,
                authors="; ".join(item.get("creators", [])[:5]) if isinstance(item.get("creators"), list) else "",
                pdf_url=pdf_url,
                landing_page_url=landing or (f"https://doi.org/{doi}" if doi else ""),
                is_oa=bool(pdf_url),
            )
        )
    return articles


def search_europe_pmc(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    query = keyword
    from_year = from_year_filter(recent_years)
    if from_year:
        query += f" AND FIRST_PDATE:[{from_year}-01-01 TO 3000-12-31]"
    data = request_json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {"query": query, "format": "json", "pageSize": min(limit, 100)},
        timeout=25,
    )
    articles = []
    for item in data.get("resultList", {}).get("result", []):
        doi = item.get("doi", "")
        pmcid = item.get("pmcid", "")
        pdf_url = f"https://europepmc.org/articles/{pmcid}?pdf=render" if pmcid else ""
        articles.append(
            normalize_article(
                source="Europe PMC",
                title=item.get("title"),
                year=item.get("pubYear"),
                doi=doi,
                journal=item.get("journalTitle", ""),
                cited_by_count=item.get("citedByCount") or 0,
                relevance_score=78,
                authors=item.get("authorString", ""),
                pdf_url=pdf_url,
                landing_page_url=f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id', '')}",
                is_oa=bool(pdf_url),
            )
        )
    return articles


def search_datacite(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    data = request_json("https://api.datacite.org/dois", {"query": keyword, "page[size]": min(limit, 100)}, timeout=25)
    from_year = from_year_filter(recent_years)
    articles = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        year = attrs.get("publicationYear") or 0
        if from_year and year and int(year) < from_year:
            continue
        creators = attrs.get("creators") or []
        authors = "; ".join((creator.get("name") or "").strip() for creator in creators[:5] if creator.get("name"))
        titles = attrs.get("titles") or []
        title = titles[0].get("title", "") if titles else ""
        doi = attrs.get("doi", "")
        articles.append(
            normalize_article(
                source="DataCite",
                title=title,
                year=year,
                doi=doi,
                journal=attrs.get("publisher", ""),
                relevance_score=50,
                authors=authors,
                landing_page_url=attrs.get("url", "") or (f"https://doi.org/{doi}" if doi else ""),
            )
        )
    return articles


def search_core(keyword: str, limit: int, recent_years: int | None) -> list[dict]:
    api_key = get_core_api_key()
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}"}
    data = request_json("https://api.core.ac.uk/v3/search/works", {"q": keyword, "limit": min(limit, 100)}, headers=headers, timeout=25)
    from_year = from_year_filter(recent_years)
    articles = []
    for item in data.get("results", []):
        year = item.get("yearPublished") or 0
        if from_year and year and int(year) < from_year:
            continue
        authors = "; ".join(author.get("name", "") for author in (item.get("authors") or [])[:5] if author.get("name"))
        download_url = item.get("downloadUrl") or ""
        articles.append(
            normalize_article(
                source="CORE",
                title=item.get("title"),
                year=year,
                doi=item.get("doi", ""),
                journal=(item.get("journals") or [{}])[0].get("title", "") if item.get("journals") else "",
                relevance_score=55,
                authors=authors,
                pdf_url=download_url,
                landing_page_url=item.get("sourceFulltextUrls", [""])[0] if item.get("sourceFulltextUrls") else "",
                is_oa=bool(download_url),
            )
        )
    return articles


SOURCE_FUNCTIONS = {
    "OpenAlex": search_openalex,
    "Semantic Scholar": search_semantic_scholar,
    "Crossref": search_crossref,
    "Google Scholar (SerpAPI)": search_google_scholar_serpapi,
    "Scopus (Elsevier API)": search_scopus,
    "ScienceDirect (Elsevier API)": search_sciencedirect,
    "Web of Science (API)": search_web_of_science,
    "Springer Nature": search_springer,
    "PubMed": search_pubmed,
    "Europe PMC": search_europe_pmc,
    "ERIC": search_eric,
    "DOAJ": search_doaj,
    "arXiv": search_arxiv,
    "CORE": search_core,
    "DataCite": search_datacite,
}


@st.cache_data(ttl=3600, show_spinner=False)
def search_articles(keyword: str, limit: int, recent_years: int | None, sources: tuple[str, ...]) -> tuple[list[dict], dict[str, str]]:
    article_lists = []
    errors = {}
    for source in sources:
        search_fn = SOURCE_FUNCTIONS.get(source)
        if not search_fn:
            continue
        try:
            article_lists.append(search_fn(keyword, limit, recent_years))
        except Exception as exc:
            errors[source] = str(exc)
    return merge_articles(article_lists, limit), errors


def pdf_filename(article: dict) -> str:
    year = article["year"] or "Unknown_Year"
    title = clean_filename(article["title"])
    return f"{year} {title}.pdf"


def action_link(label: str, url: str, class_name: str, extra_class: str = "", download_name: str = "") -> str:
    safe_label = html.escape(label)
    safe_url = html.escape(url, quote=True)
    classes = f"{class_name} {extra_class}".strip()
    download_attr = f' download="{html.escape(download_name, quote=True)}"' if download_name else ""
    return f'<a class="{classes}" href="{safe_url}" target="_blank" rel="noreferrer"{download_attr}>{safe_label}</a>'


def pdf_link_for_article(article: dict, class_name: str) -> str:
    download_name = pdf_filename(article)
    if article["pdf_url"]:
        return action_link("PDF電子檔", article["pdf_url"], class_name, "available-pdf", download_name)
    if article["doi"]:
        return action_link("PDF電子檔", f"http://www.abc.cde/{article['doi']}", class_name, "missing-pdf", download_name)
    return f'<span class="{class_name} missing-pdf disabled">PDF電子檔</span>'


def render_article_actions(article: dict, index: int) -> None:
    if not article["doi"]:
        st.caption("此筆資料沒有 DOI。")
        return

    key = f"article-{index}"
    button_class = f"action-button-{index}"
    safe_doi = html.escape(article["doi"], quote=True)
    encoded_doi = base64.b64encode(article["doi"].encode("utf-8")).decode("ascii")
    pdf_button = pdf_link_for_article(article, button_class)
    source_button = action_link("開啟來源", article["landing_page_url"], button_class) if article["landing_page_url"] else ""
    scholar_button = action_link("Google Scholar", google_scholar_url(article), button_class)

    components.html(
        f"""
        <style>
          .action-row-{index} {{
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            width: 100%;
          }}
          .doi-box-{index} {{
            background: #f6f8fa;
            border-radius: 6px;
            display: inline-flex;
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 14px;
            line-height: 1;
            padding: 13px 14px;
            white-space: nowrap;
          }}
          .{button_class} {{
            align-items: center;
            background: #fff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            box-sizing: border-box;
            color: #31333f;
            cursor: pointer;
            display: inline-flex;
            font-family: sans-serif;
            font-size: 14px;
            height: 42px;
            justify-content: center;
            line-height: 1;
            padding: 0 16px;
            text-decoration: none;
            white-space: nowrap;
          }}
          .{button_class}.missing-pdf {{
            background: #fff1f2;
            border-color: #f4b4bd;
            color: #9f1239;
          }}
          .{button_class}.available-pdf {{
            background: #ecfdf3;
            border-color: #9fd8b8;
            color: #166534;
          }}
          .{button_class}.disabled {{
            color: #a0a4ad;
            cursor: default;
            pointer-events: none;
          }}
        </style>
        <div class="action-row-{index}">
          <code class="doi-box-{index}">{safe_doi}</code>
          <button class="{button_class}" id="copy-{key}">複製</button>
          {pdf_button}
          {source_button}
          {scholar_button}
        </div>
        <script>
          const button = document.getElementById("copy-{key}");
          button.addEventListener("click", async () => {{
            const text = decodeURIComponent(escape(atob("{encoded_doi}")));
            await navigator.clipboard.writeText(text);
            button.textContent = "已複製";
            setTimeout(() => button.textContent = "複製", 1400);
          }});
        </script>
        """,
        height=58,
    )


def google_scholar_url(article: dict) -> str:
    query = article["doi"] or article["title"]
    return f"https://scholar.google.com/scholar?q={quote_plus(query)}"


def external_search_links(keyword: str) -> dict[str, str]:
    q = quote_plus(keyword)
    return {
        "Google Scholar": f"https://scholar.google.com/scholar?q={q}",
        "Web of Science": f"https://www.webofscience.com/wos/woscc/basic-search",
        "Scopus": f"https://www.scopus.com/search/form.uri",
        "CORE": f"https://core.ac.uk/search?q={q}",
        "BASE": f"https://www.base-search.net/Search/Results?lookfor={q}",
        "ResearchGate": f"https://www.researchgate.net/search/publication?q={q}",
        "SSRN": f"https://www.ssrn.com/index.cfm/en/search-results/?term={q}",
        "OSF": f"https://osf.io/search/?q={q}",
        "ScienceDirect": f"https://www.sciencedirect.com/search?qs={q}",
        "SpringerLink": f"https://link.springer.com/search?query={q}",
        "Taylor & Francis": f"https://www.tandfonline.com/action/doSearch?AllField={q}",
        "Emerald": f"https://www.emerald.com/insight/search?q={q}",
        "SAGE": f"https://journals.sagepub.com/action/doSearch?AllField={q}",
        "Wiley": f"https://onlinelibrary.wiley.com/action/doSearch?AllField={q}",
        "IEEE Xplore": f"https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={q}",
        "ACM DL": f"https://dl.acm.org/action/doSearch?AllField={q}",
        "Institutional Repositories": f"https://www.google.com/search?q={q}+filetype%3Apdf+institutional+repository",
    }


def render_external_search_links(keyword: str) -> None:
    if not keyword:
        return
    with st.expander("外部資料庫搜尋入口（需手動開啟或需要授權）", expanded=False):
        links = external_search_links(keyword)
        cols = st.columns(4)
        for idx, (label, url) in enumerate(links.items()):
            with cols[idx % 4]:
                st.link_button(label, url)


def render_article(article: dict, index: int) -> None:
    with st.container(border=True):
        top_cols = st.columns([0.7, 4.3, 1, 1, 1])
        top_cols[0].metric("年份", article["year"] or "N/A")
        top_cols[1].markdown(f"**{article['title']}**")
        top_cols[2].metric("相關性", f"{article['relevance_score']:.1f}")
        top_cols[3].metric("引用數", article["cited_by_count"])
        top_cols[4].write("OA：有" if article["is_oa"] else "OA：未確認")

        st.caption(article["authors"] or "作者資料未提供")
        if article["journal"]:
            st.write(f"期刊：{article['journal']}")
        st.caption("來源：" + "、".join(article["sources"]))

        render_article_actions(article, index)


render_login_gate()
render_logout_button()

st.title("期刊文章電子檔查找系統")
st.write("輸入研究構面或關鍵字，整合多個合法學術資料來源搜尋文章。")

with st.form("search-form"):
    cols = st.columns([3, 1, 1])
    keyword = cols[0].text_input(
        "關鍵字或研究構面",
        placeholder="例如：transformational leadership creativity",
        label_visibility="collapsed",
    )
    recent_choice = cols[1].selectbox("年份範圍", ["近 5 年", "近 3 年", "近 10 年", "不限年份"], index=0)
    limit = cols[2].selectbox("筆數", [10, 25, 50], index=1)
    selected_sources = st.multiselect("API 搜尋來源", API_SOURCES, default=DEFAULT_PUBLIC_SOURCES)
    submitted = st.form_submit_button("搜尋")

recent_year_map = {
    "近 3 年": 3,
    "近 5 年": 5,
    "近 10 年": 10,
    "不限年份": None,
}

st.info("API 來源會自動彙整與去重；Google Scholar、Web of Science、Scopus、ResearchGate、SSRN、出版社與機構典藏提供外部搜尋入口，不做爬蟲。")

if submitted and not keyword.strip():
    st.warning("請先輸入關鍵字或研究構面。")

if submitted and keyword.strip():
    render_external_search_links(keyword.strip())
    with st.spinner("正在搜尋多個學術資料來源..."):
        results, errors = search_articles(keyword.strip(), limit, recent_year_map[recent_choice], tuple(selected_sources))

    if errors:
        with st.expander("部分來源搜尋失敗"):
            for source, message in errors.items():
                st.write(f"{source}: {message}")

    if not results:
        st.warning("找不到結果，請改用英文關鍵字、同義詞或更具體的研究構面名稱，或使用外部資料庫搜尋入口。")
    else:
        st.subheader(f"搜尋結果：{keyword.strip()}")
        st.caption(f"共顯示 {len(results)} 筆。年份範圍：{recent_choice}。")
        for i, article in enumerate(results):
            render_article(article, i)
