from urllib.parse import quote

import requests
from flask import Flask, redirect, render_template, request, url_for

from paper_download import (
    SAVE_DIR,
    candidate_pdf_urls,
    clean_filename,
    download_pdf,
    get_crossref_metadata,
    log_pending,
    log_result,
    normalize_doi,
)


app = Flask(__name__)


def search_articles(keyword: str, limit: int = 25) -> list[dict]:
    url = "https://api.openalex.org/works"
    params = {
        "search": keyword,
        "filter": "type:article",
        "sort": "cited_by_count:desc",
        "per-page": limit,
    }
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()

    articles = []
    for work in response.json().get("results", []):
        doi_url = work.get("doi") or ""
        doi = doi_url.replace("https://doi.org/", "") if doi_url else ""
        best_oa = work.get("best_oa_location") or {}
        primary = work.get("primary_location") or {}
        source = (primary.get("source") or {}).get("display_name", "")

        articles.append(
            {
                "title": work.get("title") or "Untitled",
                "year": work.get("publication_year") or "",
                "doi": doi,
                "journal": source,
                "cited_by_count": work.get("cited_by_count") or 0,
                "authors": format_authors(work.get("authorships") or []),
                "pdf_url": best_oa.get("pdf_url") or "",
                "landing_page_url": best_oa.get("landing_page_url") or doi_url,
                "is_oa": bool(work.get("open_access", {}).get("is_oa")),
            }
        )
    return articles


def format_authors(authorships: list[dict]) -> str:
    names = []
    for authorship in authorships[:5]:
        author = authorship.get("author") or {}
        if author.get("display_name"):
            names.append(author["display_name"])
    if len(authorships) > 5:
        names.append("et al.")
    return "; ".join(names)


def download_by_doi(doi: str) -> tuple[bool, str]:
    doi = normalize_doi(doi)
    metadata = get_crossref_metadata(doi)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    file_name = f"{metadata['year']}_{clean_filename(metadata['title'])}.pdf"
    file_path = SAVE_DIR / file_name

    if file_path.exists():
        log_result(metadata, "已存在", filename=file_name)
        return True, f"檔案已存在：{file_name}"

    for source, pdf_url in candidate_pdf_urls(metadata):
        if download_pdf(pdf_url, file_path):
            log_result(metadata, "已下載", source=source, pdf_url=pdf_url, filename=file_name)
            return True, f"下載完成：{file_name}"

    log_result(metadata, "待取得")
    log_pending(metadata)
    return False, "找不到合法免費 PDF，已記錄到待取得清單。"


@app.get("/")
def index():
    keyword = request.args.get("q", "").strip()
    message = request.args.get("message", "")
    status = request.args.get("status", "")
    articles = []
    error = ""

    if keyword:
        try:
            articles = search_articles(keyword)
        except requests.RequestException as exc:
            error = f"搜尋失敗：{exc}"

    return render_template(
        "index.html",
        articles=articles,
        error=error,
        keyword=keyword,
        message=message,
        status=status,
    )


@app.post("/download")
def download():
    doi = request.form.get("doi", "").strip()
    keyword = request.form.get("keyword", "").strip()

    if not doi:
        return redirect(url_for("index", q=keyword, status="error", message="這筆資料沒有 DOI，無法自動下載。"))

    ok, message = download_by_doi(doi)
    return redirect(url_for("index", q=keyword, status="ok" if ok else "warn", message=message))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
