# Elephant — 台灣經濟情報系統

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟情報系統。它不只展示資料，而是每天自動抓官方資料、驗證、偵測修正、計算景氣動能／轉折／背離／廣度與 Cycle Score，再把 30 秒摘要發布到 GitHub Pages。

網站：`https://linwuyen.github.io/Elephant/`

## 打開首頁會直接看到

- **Elephant Cycle Score**：-100～+100 的透明規則式景氣分數。
- **Momentum**：景氣正在加速、持平或減速。
- **Breadth**：多少產業 YoY 為正，以及相較前月是擴散或收斂。
- **Leading**：國發會官方領先指標近 3 個月方向。
- **Official signal**：國發會景氣對策信號燈號與綜合分數。
- **Confidence**：資料來源健康度與可用元件完整度。
- **Since your last visit**：瀏覽器只在本機記住上一份摘要快照，下次直接列出實質變化。
- **Turning points**：YoY 負轉正、正轉負、收縮收斂、擴張降速、加速／減速。
- **Divergences**：科技 vs 整體製造、生產 vs 銷售、領先 vs 同時等重要背離。
- **What matters now**：把大量訊號依重大性過濾，只顯示最值得注意的項目。
- **Next watch**：根據目前訊號產生下一步觀察清單。
- **Revision log**：官方回溯修正歷史值時，保留 old/new/delta 與偵測時間。

## 自動更新

- 每天 **18:17（Asia/Taipei）** 自動檢查。
- 修改資料管線程式也會立即觸發更新。
- Workflow 使用 `concurrency.cancel-in-progress: true`，避免多個資料更新互相搶 push。
- 資料 commit 前會 fetch + rebase，避免遠端 main 有新 commit 時 non-fast-forward。
- 驗證失敗或資料過舊時不把壞值覆蓋成「健康」。
- 關鍵來源異常會自動建立／更新 GitHub Issue；恢復正常後自動關閉。
- 更新後明確 dispatch Pages，不依賴 bot commit 再觸發另一條 workflow。

## 官方資料來源

| 來源 | 狀態 | 主要用途 |
| --- | --- | --- |
| 主計總處來源資料 | 自動、必要 | GDP、經濟成長率、CPI、產業 GDP |
| 經濟部統計處 | 自動、必要 | 工業生產、現行製造業銷售指數、主要產業 |
| 內政部戶政司 | 自動、必要 | 人口、出生死亡、年齡結構、縣市、高齡化 |
| 國家發展委員會 | 自動、必要 | 領先／同時／落後指標、景氣燈號、PMI/NMI、M1B、出口、失業率、利率、存貨、半導體設備進口等景氣構成項目 |
| 經濟部 legacy 下載 | Best effort | 舊銷售價值／投資等歷史補充；端點失效保留 last-good |
| SEGIS | Blocked | schema/status 保留；沒有穩定可驗證官方輸入前不偽造數值 |

國發會官方資料集說明指出，領先指標用來預判未來景氣，而景氣指標資料在每月發布時可能回溯修正歷史值；Elephant 因此同時做 freshness 與 revision tracking。

## Intelligence pipeline

```text
DGBAS / MOEA / RIS / NDC
          ↓
官方資料抓取
          ↓
revision_tracker.capture()
          ↓
格式、值域、period、freshness 驗證
          ↓
data/*.json
          ↓
revision diff：old → new
          ↓
build_summary.py
          ↓
YoY / acceleration / MA3 / MA6 / 12M percentile
          ↓
Breadth / Turning points / Divergences
          ↓
Cycle Score / Momentum / Confidence
          ↓
重大性過濾 / Next watch / Evidence chain
          ↓
GitHub Pages
```

## Cycle Score

Cycle Score 是 Elephant 自訂的透明綜合分數，**不是國發會官方景氣燈號**。

目前元件：

- 製造業生產 YoY：30%
- 產業正成長廣度：20%
- 製造業銷售 YoY：15%
- 國發會領先指標 3M：20%
- PMI：10%
- GDP 成長率：5%

缺值時只用可用元件重新正規化權重。每個元件的 raw value、轉換後 score、weight 都可在首頁展開查看。

## 轉折偵測

對主要產業自動計算：

- 同月 YoY
- 前月 YoY
- YoY acceleration（百分點）
- 3M / 6M YoY moving average
- 最新 YoY 在過去 12 個月的 percentile
- 負轉正 / 正轉負
- 收縮快速收斂
- 擴張明顯降速
- 加速 / 減速

## 背離偵測

目前自動監看：

- 資訊電子 vs 整體製造業
- 製造業生產 vs 製造業銷售
- 國發會領先 vs 同時指標

背離只在差距達到門檻時顯示，避免把普通波動當成訊號。

## Since your last visit

前端使用 `localStorage` 保存上一份摘要的**核心指標快照**，不保存個資、不需要登入，也不傳回伺服器。

新摘要會先產生穩定 fingerprint：

- fingerprint 相同 → 顯示沒有實質變化。
- fingerprint 不同 → 比較共通核心指標，按變動重要度排序。
- 第一次造訪 → 建立 baseline。

## Revision / vintage

`data/revisions.json` 保存同一個 period 的官方數值被回溯修改時的：

- source
- dataset / series
- period
- old
- new
- delta
- detected_at

Git 本身仍保留每次發布版本，所以 revision log + Git history 可以一起做稽核。

## 資料完整性

發布前檢查包括：

- JSON 可解析。
- 必要序列存在。
- period 不重複、排序正常。
- GDP／人口／產業指數合理值域。
- 最新縣市至少 20 個行政區。
- DGBAS / RIS 年資料至少到前一曆年。
- MOEA 核心月資料與銷售指數不得落後超過 4 個月。
- NDC 領先／同時指標不得落後超過 4 個月。
- Cycle Score、Momentum、Confidence、Turning point、Divergence 皆通過 schema/value validation。
- 單一來源失敗時保留 last-good data，不把 HTML、DNS 錯誤或欄位漂移當成正式數據。

## 生成式 AI 的角色

目前**不使用生成式 AI 決定數字、趨勢或分數**。所有判讀先由 deterministic engine 產生，確保同一份資料得到同一個結果。

未來即使接 LLM，也只適合放在最上層做自然語言解釋：

```text
官方資料 → 規則式 Facts / Signals / Scores → LLM 解釋
```

而不是讓 LLM 自己決定「事實是多少」。

## 本機不是必要條件

日常使用、抓取、驗證、revision tracking、摘要、告警、commit 與 Pages 部署都在 GitHub 雲端完成。網站不依賴任何使用者電腦常駐。
