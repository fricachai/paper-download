import base64
import html
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components

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


st.set_page_config(
    page_title="期刊文章電子檔查找系統",
    page_icon="📄",
    layout="wide",
)


def format_authors(authorships: list[dict]) -> str:
    names = []
    for authorship in authorships[:5]:
        author = authorship.get("author") or {}
        if author.get("display_name"):
            names.append(author["display_name"])
    if len(authorships) > 5:
        names.append("et al.")
    return "; ".join(names)


def normalize_relevance(work: dict) -> float:
    score = work.get("relevance_score")
    if isinstance(score, int | float):
        return float(score)
    return 0.0


@st.cache_data(ttl=3600, show_spinner=False)
def search_articles(keyword: str, limit: int = 25, recent_years: int | None = 5) -> list[dict]:
    url = "https://api.openalex.org/works"
    filters = ["type:article"]
    if recent_years:
        from_year = datetime.now().year - recent_years + 1
        filters.append(f"from_publication_date:{from_year}-01-01")

    params = {
        "search": keyword,
        "filter": ",".join(filters),
        "per-page": min(max(limit * 2, 25), 200),
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
        year = work.get("publication_year") or 0

        articles.append(
            {
                "title": work.get("title") or "Untitled",
                "year": year,
                "doi": doi,
                "journal": source,
                "cited_by_count": work.get("cited_by_count") or 0,
                "relevance_score": normalize_relevance(work),
                "authors": format_authors(work.get("authorships") or []),
                "pdf_url": best_oa.get("pdf_url") or "",
                "landing_page_url": best_oa.get("landing_page_url") or doi_url,
                "is_oa": bool(work.get("open_access", {}).get("is_oa")),
            }
        )

    articles.sort(key=lambda item: (-item["relevance_score"], -int(item["year"] or 0)))
    return articles[:limit]


def build_filename(metadata: dict) -> str:
    return f"{metadata['year']}_{clean_filename(metadata['title'])}.pdf"


def ensure_pdf_file(doi: str) -> tuple[bool, str, str]:
    doi = normalize_doi(doi)
    metadata = get_crossref_metadata(doi)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    file_name = build_filename(metadata)
    file_path = SAVE_DIR / file_name

    if file_path.exists():
        log_result(metadata, "已存在", filename=file_name)
        return True, f"檔案已存在：{file_name}", str(file_path)

    for source, pdf_url in candidate_pdf_urls(metadata):
        if download_pdf(pdf_url, file_path):
            log_result(metadata, "已下載", source=source, pdf_url=pdf_url, filename=file_name)
            return True, f"下載完成：{file_name}", str(file_path)

    log_result(metadata, "待取得")
    log_pending(metadata)
    return False, "找不到合法免費 PDF，已記錄到待取得清單。", ""


def copy_doi_button(doi: str, key: str) -> None:
    safe_doi = html.escape(doi, quote=True)
    encoded = base64.b64encode(doi.encode("utf-8")).decode("ascii")
    components.html(
        f"""
        <div style="display:flex;align-items:center;gap:8px;width:100%;">
          <code style="flex:1;background:#f6f8fa;border-radius:6px;padding:11px 12px;display:block;white-space:nowrap;overflow:auto;">{safe_doi}</code>
          <button id="copy-{key}" style="border:1px solid #d0d7de;border-radius:6px;background:white;padding:9px 12px;cursor:pointer;">複製</button>
        </div>
        <script>
          const button = document.getElementById("copy-{key}");
          button.addEventListener("click", async () => {{
            const text = decodeURIComponent(escape(atob("{encoded}")));
            await navigator.clipboard.writeText(text);
            button.textContent = "已複製";
            setTimeout(() => button.textContent = "複製", 1400);
          }});
        </script>
        """,
        height=52,
    )


def render_download_controls(article: dict, index: int) -> None:
    prepared_key = f"prepared-{index}"
    if article["doi"]:
        if st.button("查找合法 PDF", key=f"prepare-{index}"):
            with st.spinner("正在查找並準備 PDF..."):
                ok, message, file_path = ensure_pdf_file(article["doi"])
            st.session_state[prepared_key] = {
                "ok": ok,
                "message": message,
                "file_path": file_path,
            }

        prepared = st.session_state.get(prepared_key)
        if prepared:
            if prepared["ok"]:
                st.success(prepared["message"])
                with open(prepared["file_path"], "rb") as file:
                    st.download_button(
                        "下載合法 PDF",
                        data=file,
                        file_name=prepared["file_path"].split("\\")[-1].split("/")[-1],
                        mime="application/pdf",
                        key=f"download-{index}",
                    )
            else:
                st.warning(prepared["message"])
    else:
        st.button("無 DOI", key=f"no-doi-{index}", disabled=True)

    if article["landing_page_url"]:
        st.link_button("開啟來源", article["landing_page_url"])


def render_article(article: dict, index: int) -> None:
    with st.container(border=True):
        top_cols = st.columns([0.7, 4.6, 1, 1, 1])
        top_cols[0].metric("年份", article["year"] or "N/A")
        top_cols[1].markdown(f"**{article['title']}**")
        top_cols[2].metric("相關性", f"{article['relevance_score']:.1f}")
        top_cols[3].metric("引用數", article["cited_by_count"])
        top_cols[4].write("OA：有" if article["is_oa"] else "OA：未確認")

        st.caption(article["authors"] or "作者資料未提供")
        if article["journal"]:
            st.write(f"期刊：{article['journal']}")

        if article["doi"]:
            doi_cols = st.columns([4, 1])
            with doi_cols[0]:
                copy_doi_button(article["doi"], f"{index}")
            with doi_cols[1]:
                st.link_button("DOI 網址", f"https://doi.org/{article['doi']}")
        else:
            st.caption("此筆資料沒有 DOI。")

        action_cols = st.columns([1.1, 5])
        with action_cols[0]:
            render_download_controls(article, index)


st.title("期刊文章電子檔查找系統")
st.write("輸入研究構面或關鍵字，優先列出相關性高且年份新的文章，並嘗試下載合法免費全文 PDF。")

with st.form("search-form"):
    cols = st.columns([4, 1, 1])
    keyword = cols[0].text_input(
        "關鍵字或研究構面",
        placeholder="例如：transformational leadership creativity",
        label_visibility="collapsed",
    )
    recent_choice = cols[1].selectbox("年份範圍", ["近 5 年", "近 3 年", "近 10 年", "不限年份"], index=0)
    limit = cols[2].selectbox("筆數", [10, 25, 50], index=1)
    submitted = st.form_submit_button("搜尋")

recent_year_map = {
    "近 3 年": 3,
    "近 5 年": 5,
    "近 10 年": 10,
    "不限年份": None,
}

st.info("排序規則：先依 OpenAlex 相關性分數由高到低，再依年份由新到舊。PDF 只會從合法免費來源下載。")

if submitted and not keyword.strip():
    st.warning("請先輸入關鍵字或研究構面。")

if submitted and keyword.strip():
    with st.spinner("正在搜尋文章..."):
        try:
            results = search_articles(keyword.strip(), limit, recent_year_map[recent_choice])
        except requests.RequestException as exc:
            st.error(f"搜尋失敗：{exc}")
            results = []

    if not results:
        st.warning("找不到結果，請改用英文關鍵字、同義詞或更具體的研究構面名稱。")
    else:
        st.subheader(f"搜尋結果：{keyword.strip()}")
        st.caption(f"共顯示 {len(results)} 筆。年份範圍：{recent_choice}。")
        for i, article in enumerate(results):
            render_article(article, i)
