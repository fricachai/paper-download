# Paper Download

依 DOI 批次查找期刊文章 metadata，並從合法免費來源下載可公開取得的全文 PDF。

## 功能

- 透過 Crossref 取得文章年份與篇名
- 透過 OpenAlex、Unpaywall、Crossref link 查找開放取用 PDF
- 下載 PDF 到 `01_全文PDF`
- 檔名格式：`西元年份四碼_英文篇名或中文篇名.pdf`
- 找不到合法免費全文時，寫入 `03_待取得全文/待取得全文.csv`
- 所有處理結果寫入 `02_查找紀錄/文獻查找清單.csv`

## 安裝

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 使用

將 DOI 放入 `config/dois.txt`，一行一筆：

```text
10.1016/j.chb.2021.106722
10.1038/s41586-020-2649-2
```

執行：

```powershell
python paper_download.py
```

## 啟動 Web 介面

執行：

```powershell
python app.py
```

開啟：

```text
http://127.0.0.1:5000
```

在搜尋框輸入研究構面或關鍵字，系統會依引用數排序列出文章，並可針對有 DOI 的文章嘗試下載合法免費 PDF。

如要使用 Unpaywall，建議設定 email：

```powershell
$env:UNPAYWALL_EMAIL="your-email@example.com"
python paper_download.py
```

## 合法來源限制

本工具僅查找與下載合法免費全文來源，例如出版社開放取用頁面、作者自存稿、機構典藏、OpenAlex、Unpaywall、Crossref 回傳的開放 PDF 連結等。若找不到合法免費全文，系統只會記錄待取得，不會使用未授權來源。
