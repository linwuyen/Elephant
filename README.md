# Elephant — 台灣經濟資料庫

公開的 GitHub Pages 儀表板，快速檢視台灣 GDP、CPI、人口結構、縣市老化與主要產業生產指數。

## 網站

https://linwuyen.github.io/Elephant/

## 內容

- 名目 GDP、經濟成長率、CPI 年增率
- 1990–2025 人口、高齡人口占比、出生與死亡趨勢
- 2025 年 22 縣市人口與老化指數
- 工業、製造業、資訊電子、電子零組件、積體電路、封測、電腦光學等主要產業指數
- 響應式手機與桌面介面

## 資料來源

行政院主計總處、經濟部統計處、內政部戶政司。

目前網頁為快速檢視版；完整 SQLite 資料庫另存於 Google Drive。SEGIS 尚未取得可驗證觀測值，因此未標示為已完成資料。

## 部署

`.github/workflows/pages.yml` 會在 `main` 更新時自動部署 GitHub Pages。
