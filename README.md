# Paper Download

期刊文章電子檔查找系統。可用 Streamlit Web 介面輸入關鍵字搜尋文章，也可用 DOI 批次查找合法免費全文 PDF。

## 功能

- 用關鍵字或研究構面搜尋期刊文章
- 搜尋結果先依相關性由高到低排序，再依年份由新到舊排序
- 預設搜尋近 5 年文章，可改為近 3 年、近 10 年或不限年份
- 顯示年份、篇名、作者、期刊、相關性、引用數、DOI、OA 狀態
- 每篇文章只列出出版社/文章頁 metadata 提供的原文 Keywords；若無法取得則顯示未取得，不使用 OpenAlex 推論分類替代
- DOI 旁提供複製按鈕
- 透過 OpenAlex、Unpaywall、Crossref 查找合法開放 PDF
- PDF 存到 `01_全文PDF`
- 檔名格式：`西元年份四碼_英文篇名或中文篇名.pdf`
- 找不到合法免費全文時，寫入 `03_待取得全文/待取得全文.csv`
- 所有處理結果寫入 `02_查找紀錄/文獻查找清單.csv`

## 本機安裝

```powershell
git clone https://github.com/fricachai/paper-download.git
cd paper-download
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 啟動 Streamlit Web 介面

```powershell
streamlit run streamlit_app.py
```

啟動後開啟：

```text
http://localhost:8501
```

可輸入：

```text
transformational leadership creativity
knowledge sharing
technology acceptance model
brand trust
```

## DOI 批次下載

將 DOI 放入 `config/dois.txt`，一行一筆：

```text
10.1016/j.chb.2021.106722
10.1038/s41586-020-2649-2
```

執行：

```powershell
python paper_download.py
```

## Unpaywall Email

如要使用 Unpaywall，建議設定 email：

```powershell
$env:UNPAYWALL_EMAIL="your-email@example.com"
streamlit run streamlit_app.py
```

## 部署到 Streamlit Cloud

1. 開啟 [Streamlit Community Cloud](https://share.streamlit.io/)
2. 使用 GitHub 帳號登入
3. 選擇 repository：`fricachai/paper-download`
4. Branch 選 `main`
5. Main file path 填入：

```text
streamlit_app.py
```

6. 按 Deploy

部署完成後，Streamlit 會產生公開網址。

## 合法來源限制

本工具僅查找與下載合法免費全文來源，例如出版社開放取用頁面、作者自存稿、機構典藏、OpenAlex、Unpaywall、Crossref 回傳的開放 PDF 連結等。若找不到合法免費全文，系統只會記錄待取得，不會使用未授權來源。
