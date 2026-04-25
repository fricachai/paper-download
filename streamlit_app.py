import base64
import html
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components


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


def action_link(label: str, url: str, class_name: str, extra_class: str = "") -> str:
    safe_label = html.escape(label)
    safe_url = html.escape(url, quote=True)
    classes = f"{class_name} {extra_class}".strip()
    return f'<a class="{classes}" href="{safe_url}" target="_blank" rel="noreferrer">{safe_label}</a>'


def pdf_link_for_article(article: dict, class_name: str) -> str:
    if article["pdf_url"]:
        return action_link("PDF電子檔", article["pdf_url"], class_name)
    if article["doi"]:
        return action_link("PDF電子檔", f"http://localhost:8000/{article['doi']}", class_name, "missing-pdf")
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

        render_article_actions(article, index)


st.title("期刊文章電子檔查找系統")
st.write("輸入研究構面或關鍵字，優先列出相關性高且年份新的文章。")

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

st.info("排序規則：先依 OpenAlex 相關性分數由高到低，再依年份由新到舊。有合法開放 PDF 時按鈕直接開 PDF；沒有合法 PDF URL 時，淡紅色按鈕會開啟本機 localhost:8000 DOI 路徑。")

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
