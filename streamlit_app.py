import requests
import streamlit as st

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


@st.cache_data(ttl=3600, show_spinner=False)
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


def download_by_doi(doi: str) -> tuple[bool, str, str]:
    doi = normalize_doi(doi)
    metadata = get_crossref_metadata(doi)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    file_name = f"{metadata['year']}_{clean_filename(metadata['title'])}.pdf"
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


def render_article(article: dict, index: int) -> None:
    with st.container(border=True):
        top_cols = st.columns([0.8, 5, 1.1, 1.1])
        top_cols[0].metric("年份", article["year"] or "N/A")
        top_cols[1].markdown(f"**{article['title']}**")
        top_cols[2].metric("引用數", article["cited_by_count"])
        top_cols[3].write("OA：有" if article["is_oa"] else "OA：未確認")

        st.caption(article["authors"] or "作者資料未提供")
        if article["journal"]:
            st.write(f"期刊：{article['journal']}")
        if article["doi"]:
            st.code(article["doi"], language=None)

        action_cols = st.columns([1.1, 1.1, 4])
        if article["doi"]:
            if action_cols[0].button("下載合法 PDF", key=f"download-{index}"):
                with st.spinner("正在查找合法免費 PDF..."):
                    ok, message, file_path = download_by_doi(article["doi"])
                if ok:
                    st.success(message)
                    with open(file_path, "rb") as file:
                        st.download_button(
                            "下載到本機",
                            data=file,
                            file_name=file_path.split("\\")[-1].split("/")[-1],
                            mime="application/pdf",
                            key=f"browser-download-{index}",
                        )
                else:
                    st.warning(message)
        else:
            action_cols[0].button("無 DOI", key=f"no-doi-{index}", disabled=True)

        if article["landing_page_url"]:
            action_cols[1].link_button("開啟來源", article["landing_page_url"])


st.title("期刊文章電子檔查找系統")
st.write("輸入研究構面或關鍵字，依引用數排序搜尋期刊文章，並嘗試下載合法免費全文 PDF。")

with st.form("search-form"):
    cols = st.columns([5, 1.2])
    keyword = cols[0].text_input(
        "關鍵字或研究構面",
        placeholder="例如：transformational leadership creativity",
        label_visibility="collapsed",
    )
    limit = cols[1].selectbox("筆數", [10, 25, 50], index=1)
    submitted = st.form_submit_button("搜尋")

st.info("本系統僅下載合法免費全文來源。找不到 PDF 時會記錄待取得，可再透過圖書館、館際合作或聯繫作者取得。")

if submitted and not keyword.strip():
    st.warning("請先輸入關鍵字或研究構面。")

if submitted and keyword.strip():
    with st.spinner("正在搜尋文章..."):
        try:
            results = search_articles(keyword.strip(), limit)
        except requests.RequestException as exc:
            st.error(f"搜尋失敗：{exc}")
            results = []

    if not results:
        st.warning("找不到結果，請改用英文關鍵字、同義詞或更具體的研究構面名稱。")
    else:
        st.subheader(f"搜尋結果：{keyword.strip()}")
        st.caption(f"共顯示 {len(results)} 筆，排序依 OpenAlex 引用數由高到低。")
        for i, article in enumerate(results):
            render_article(article, i)
