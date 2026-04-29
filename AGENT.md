# AGENT.md

## Project

Repository: `fricachai/paper-download`

Local workspace:

```text
D:\USB_Data\個人研究\實用分析分類\ChatGPT_個人累積\ChatGPT_Codex_專案資料夾\找尋文章的電子檔
```

This project is a Streamlit web app for searching journal articles by keyword/research construct, ranking results, showing DOI/source/PDF actions, and supporting DOI batch PDF lookup.

## Current App

Main Streamlit file:

```text
streamlit_app.py
```

Run locally:

```powershell
streamlit run streamlit_app.py
```

Local URL:

```text
http://127.0.0.1:8501
```

## Login

The app has a Streamlit login gate adapted from `LOGIN_GATE_REUSE.md`.

Default login:

```text
username: frica
password: stock2026
```

Can be overridden in Streamlit Secrets:

```toml
AUTH_USERNAMES = ["frica"]
AUTH_PASSWORD = "stock2026"
```

## Search Sources

The app supports automatic searching through legal/public or official API sources:

- OpenAlex
- Semantic Scholar
- Crossref
- PubMed
- Europe PMC
- ERIC
- DOAJ
- arXiv
- DataCite
- CORE, requires `CORE_API_KEY`
- Google Scholar via SerpAPI, requires `SERPAPI_KEY`
- Scopus via Elsevier API, requires `ELSEVIER_API_KEY`
- ScienceDirect via Elsevier API, requires `ELSEVIER_API_KEY`
- Web of Science via Clarivate API, requires `WOS_API_KEY`
- Springer Nature, requires `SPRINGER_API_KEY`

Default selected sources are the no-key public sources.

Optional Streamlit Secrets:

```toml
SERPAPI_KEY = "..."
ELSEVIER_API_KEY = "..."
WOS_API_KEY = "..."
SPRINGER_API_KEY = "..."
CORE_API_KEY = "..."
```

Google Scholar, Web of Science, Scopus, ResearchGate, SSRN, and publisher sites must not be scraped directly. Use official APIs or external links only.

## PDF Buttons

Each article row has:

- DOI text
- Copy button
- `PDF電子檔`
- `開啟來源`
- `Google Scholar`

PDF button behavior:

- If a legal/open PDF URL is available from the API result, the button is light green and opens that PDF.
- If no legal PDF URL is available, the button is light red and opens:

```text
http://localhost:8000/{DOI}
```

Do not change this to Sci-Hub, pismin.com, or similar unauthorized full-text sources.

## Filename Rule

Downloaded PDF filename rule:

```text
年份 篇名.pdf
```

Example:

```text
2020 Array programming with NumPy.pdf
```

The UI `PDF電子檔` link sets the HTML `download` attribute using this naming rule when the browser honors it.

The DOI batch downloader also uses this rule.

## Batch DOI Downloader

File:

```text
paper_download.py
```

Input DOI list:

```text
config/dois.txt
```

Run:

```powershell
python paper_download.py
```

Output folders:

```text
01_全文PDF
02_查找紀錄
03_待取得全文
```

## Important Constraints

Do not implement or link to unauthorized article download sources, including Sci-Hub mirrors or equivalent DOI-to-PDF bypass sites.

Do not scrape Google Scholar, Web of Science, Scopus, ResearchGate, or paywalled publisher databases directly. Use official APIs, authorized API keys, or external/manual search links.

Keep Streamlit widgets uniquely keyed when using repeated rows. Previous issue: duplicate disabled buttons caused `StreamlitDuplicateElementId`.

Avoid mixing `components.html` iframe content with separate Streamlit columns for the same action row; use one flex row to prevent button overlap.

## Recent Decisions

- Article keywords were removed entirely from results.
- Abstracts are not displayed.
- Search results rank by relevance first, then newer year.
- Login allows only `frica` by default.
- Missing PDF fallback is `http://localhost:8000/{DOI}`.
- Green PDF button means legal/open PDF URL exists.
- Red PDF button means no legal/open PDF URL was found by the API.

## Git Notes

Remote repository:

```text
https://github.com/fricachai/paper-download
```

Before pushing, run:

```powershell
git status -sb
git pull --rebase origin main
python -m py_compile streamlit_app.py paper_download.py
git push
```

Be careful: remote changes previously reintroduced unauthorized `pismin.com` links. Always check:

```powershell
Select-String -Path streamlit_app.py -Pattern 'pismin|sci-hub'
```

There should be no matches.
