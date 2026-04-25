import csv
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests


DOI_FILE = Path("config/dois.txt")
SAVE_DIR = Path("01_全文PDF")
LOG_FILE = Path("02_查找紀錄/文獻查找清單.csv")
PENDING_FILE = Path("03_待取得全文/待取得全文.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}


def clean_filename(name: str) -> str:
    """Remove characters that are invalid in Windows/macOS/Linux filenames."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:180] or "Unknown_Title"


def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi


def read_dois() -> list[str]:
    if not DOI_FILE.exists():
        return []

    dois = []
    for line in DOI_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            dois.append(normalize_doi(line))
    return dois


def request_json(url: str, params: dict | None = None) -> dict | None:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        return None
    return None


def get_crossref_metadata(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    data = request_json(url)
    if not data or "message" not in data:
        return {
            "year": "Unknown_Year",
            "title": clean_filename(doi.replace("/", "_")),
            "authors": "",
            "journal": "",
            "doi": doi,
            "crossref_links": [],
        }

    msg = data["message"]
    title = clean_filename((msg.get("title") or ["Unknown_Title"])[0])
    year = get_year(msg)
    authors = "; ".join(format_author(author) for author in msg.get("author", [])[:8])
    journal = (msg.get("container-title") or [""])[0]
    links = [link.get("URL") for link in msg.get("link", []) if link.get("URL")]

    return {
        "year": str(year),
        "title": title,
        "authors": authors,
        "journal": journal,
        "doi": doi,
        "crossref_links": links,
    }


def get_year(crossref_message: dict) -> str:
    for key in ("published-print", "published-online", "published", "created"):
        date_parts = crossref_message.get(key, {}).get("date-parts")
        if date_parts and date_parts[0]:
            return str(date_parts[0][0])
    return "Unknown_Year"


def format_author(author: dict) -> str:
    given = author.get("given", "")
    family = author.get("family", "")
    return f"{given} {family}".strip()


def get_openalex_pdf_url(doi: str) -> str | None:
    url = f"https://api.openalex.org/works/doi:{quote(doi, safe='')}"
    data = request_json(url)
    if not data:
        return None

    locations = []
    best = data.get("best_oa_location")
    if best:
        locations.append(best)
    locations.extend(data.get("oa_locations") or [])

    for location in locations:
        pdf_url = location.get("pdf_url")
        if pdf_url:
            return pdf_url
    return None


def get_unpaywall_pdf_url(doi: str) -> str | None:
    email = os.getenv("UNPAYWALL_EMAIL", "research@example.com")
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}"
    data = request_json(url, params={"email": email})
    if not data:
        return None

    locations = []
    best = data.get("best_oa_location")
    if best:
        locations.append(best)
    locations.extend(data.get("oa_locations") or [])

    for location in locations:
        pdf_url = location.get("url_for_pdf")
        if pdf_url:
            return pdf_url
    return None


def candidate_pdf_urls(metadata: dict) -> list[tuple[str, str]]:
    candidates = []

    openalex_url = get_openalex_pdf_url(metadata["doi"])
    if openalex_url:
        candidates.append(("OpenAlex", openalex_url))

    unpaywall_url = get_unpaywall_pdf_url(metadata["doi"])
    if unpaywall_url:
        candidates.append(("Unpaywall", unpaywall_url))

    for url in metadata.get("crossref_links", []):
        if looks_like_pdf_url(url):
            candidates.append(("Crossref", url))

    return dedupe_candidates(candidates)


def looks_like_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf") or "pdf" in parsed.path.lower()


def dedupe_candidates(candidates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    deduped = []
    for source, url in candidates:
        if url not in seen:
            seen.add(url)
            deduped.append((source, url))
    return deduped


def download_pdf(url: str, destination: Path) -> bool:
    try:
        with requests.get(url, headers=HEADERS, timeout=40, stream=True, allow_redirects=True) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
            first_chunk = next(resp.iter_content(chunk_size=8192), b"")

            if "application/pdf" not in content_type and not first_chunk.startswith(b"%PDF"):
                return False

            with destination.open("wb") as file:
                file.write(first_chunk)
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
        return True
    except (requests.RequestException, StopIteration):
        return False


def ensure_csv_header(path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    ensure_csv_header(path, fieldnames)
    with path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writerow(row)


def log_result(metadata: dict, status: str, source: str = "", pdf_url: str = "", filename: str = "") -> None:
    fields = [
        "研究構面/關鍵字",
        "文章年份",
        "文章題名",
        "作者",
        "期刊名稱",
        "索引/等級",
        "引用數",
        "DOI",
        "全文狀態",
        "合法全文來源URL",
        "本機檔名",
        "備註",
    ]
    append_csv(
        LOG_FILE,
        fields,
        {
            "研究構面/關鍵字": "",
            "文章年份": metadata["year"],
            "文章題名": metadata["title"],
            "作者": metadata["authors"],
            "期刊名稱": metadata["journal"],
            "索引/等級": "",
            "引用數": "",
            "DOI": metadata["doi"],
            "全文狀態": status,
            "合法全文來源URL": pdf_url,
            "本機檔名": filename,
            "備註": source,
        },
    )


def log_pending(metadata: dict) -> None:
    fields = ["文章年份", "文章題名", "作者", "期刊名稱", "DOI", "備註"]
    append_csv(
        PENDING_FILE,
        fields,
        {
            "文章年份": metadata["year"],
            "文章題名": metadata["title"],
            "作者": metadata["authors"],
            "期刊名稱": metadata["journal"],
            "DOI": metadata["doi"],
            "備註": "找不到合法免費全文 PDF，建議透過圖書館、館際合作或聯繫作者取得。",
        },
    )


def download_papers() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    dois = read_dois()

    if not dois:
        print(f"找不到 DOI。請在 {DOI_FILE} 放入 DOI，一行一筆。")
        return

    for doi in dois:
        print(f"\n處理中: {doi}")
        metadata = get_crossref_metadata(doi)
        file_name = f"{metadata['year']}_{metadata['title']}.pdf"
        file_path = SAVE_DIR / file_name

        if file_path.exists():
            print(f"  [-] 檔案已存在，跳過: {file_name}")
            log_result(metadata, "已存在", filename=file_name)
            continue

        downloaded = False
        for source, pdf_url in candidate_pdf_urls(metadata):
            print(f"  [+] 嘗試合法來源 {source}: {pdf_url}")
            if download_pdf(pdf_url, file_path):
                print(f"  [v] 下載完成: {file_name}")
                log_result(metadata, "已下載", source=source, pdf_url=pdf_url, filename=file_name)
                downloaded = True
                break
            print("  [!] 此來源未能取得 PDF。")

        if not downloaded:
            print("  [!] 找不到合法免費全文 PDF，已記錄待取得。")
            log_result(metadata, "待取得")
            log_pending(metadata)

        sleep_time = random.uniform(1, 3)
        print(f"  [z] 暫停 {sleep_time:.1f} 秒...")
        time.sleep(sleep_time)


if __name__ == "__main__":
    download_papers()
