# Published web data

這個目錄是 Elephant GitHub Pages 的發布資料層，由 `scripts/update_data.py` 產生。

不要手工修改數值。官方來源抓取成功且 `scripts/validate_data.py` 驗證通過後，GitHub Actions 才會提交變更。

`status.json` 是資料新鮮度與來源健康狀態的單一真實來源；SEGIS 在未取得可驗證觀測值前維持 blocked。
