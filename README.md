# Elephant — 台灣經濟情報系統

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟情報系統。它每天自動抓官方資料、驗證、偵測歷史修正、計算景氣動能／轉折／背離／廣度與 Cycle Score，再把 30 秒摘要發布到 GitHub Pages。

網站：`https://linwuyen.github.io/Elephant/`

## 打開首頁會直接看到

- **Elephant Cycle Score**：-100～+100 的透明規則式景氣分數。
- **Momentum**：景氣正在加速、持平或減速。
- **Breadth**：多少產業 YoY 為正，以及相較前月是擴散或收斂。
- **Leading**：國發會官方領先指標近 3 個月方向。
- **Official signal**：國發會景氣燈號與綜合分數。
- **Confidence**：資料來源健康度與可用元件完整度。
- **Since your last visit**：只在瀏覽器本機記住上一份摘要快照，下次直接列實質變化。
- **Turning points**：YoY 負轉正、正轉負、收縮收斂、擴張降速、加速／減速。
- **Divergences**：科技 vs 整體製造、生產 vs 銷售、領先 vs 同時等背離。
- **What matters now**：依重大性過濾，只顯示值得注意的項目。
- **Next watch**：根據目前訊號產生下一步觀察清單。
- **Revision log**：官方回溯修正歷史值時，保留 old/new/delta 與偵測時間。

所有數字與分類均由 deterministic engine 從已驗證資料產生；生成式 AI 不決定任何事實或分數。

## Cycle Score：同一套月度公式

為了讓今天的分數可以和歷史真正比較，Cycle Score 只使用月度／高頻成分，不再把一年一次的 GDP 混入月度計分。GDP 仍保留為總體背景資訊。

| 元件 | 權重 |
| --- | ---: |
| 製造業生產 YoY | 30% |
| 產業正成長 Breadth | 20% |
| 國發會領先指標近 3M | 20% |
| 製造業銷售 YoY | 15% |
| PMI | 10% |
| 國發會景氣綜合分數 | 5% |

缺值時只對可用元件重新正規化權重。Elephant Cycle Score 是自訂透明分數，**不是**國發會官方景氣燈號。

## 情報歷史

網站「情報歷史」頁直接提供：

- Cycle Score / Momentum 歷史時間軸
- Regime changes
- 每次核心資料版本真的改變時留下的情報快照
- 官方歷史值 revision table
- Cycle Score CSV 下載

`data/intelligence_history.json` 同時保存兩種概念：

1. **Historical reconstruction**：用目前官方已修訂序列，以同一套月度公式回算歷史分數，適合比較景氣位置與轉折。
2. **Versioned snapshots**：資料 fingerprint 真正改變才新增一筆，保留當時 Elephant 看見的摘要與主要指標。

歷史重建不是 real-time vintage backtest；真正的版本差異由 snapshots + `data/revisions.json` + Git history 留存。

## 自動更新

- 每天 **18:17（Asia/Taipei）** 自動檢查。
- 修改資料管線也會立即觸發更新。
- Workflow 使用 concurrency cancellation，避免多個更新互搶 push。
- 資料 commit 前 fetch + rebase，避免 non-fast-forward。
- 任一關鍵來源異常時保留上一版，不把壞值覆蓋成健康資料。
- 驗證成功後 bot commit `data/**`，再明確 dispatch Pages。
- 關鍵來源失敗時自動建立／更新 GitHub Issue；恢復後自動關閉。
- 每日 heartbeat 降低 scheduled workflow 因 repository 長期無 activity 被停用的風險。

## 官方資料來源

| 來源 | 狀態 | 主要用途 |
| --- | --- | --- |
| 主計總處來源資料 | 自動、必要 | GDP、經濟成長率、CPI、產業 GDP |
| 經濟部統計處 | 自動、必要 | 工業生產、製造業銷售、主要產業 |
| 內政部戶政司 | 自動、必要 | 人口、出生死亡、年齡結構、縣市、高齡化 |
| 國家發展委員會 | 自動、必要 | 領先／同時／落後指標、景氣燈號、PMI/NMI、M1B、出口、失業率、利率、存貨等景氣構成項目 |
| 經濟部 legacy 下載 | Best effort | 舊銷售價值／投資等歷史補充；失效時保留 last-good |
| SEGIS | Blocked | 沒有穩定可驗證官方輸入前不偽造數值 |

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
build_history.py
          ↓
月度 Cycle Score / Momentum 歷史重建 + 版本快照
          ↓
validate_data.py
          ↓
GitHub Pages
```

## 資料完整性

發布前至少檢查：

- JSON 可解析、必要序列存在。
- period 不重複、排序正常。
- GDP／人口／產業指數合理值域。
- 最新縣市至少 20 個行政區。
- DGBAS / RIS 年資料至少到前一曆年。
- MOEA / NDC 核心月資料不得落後超過 4 個月。
- Cycle Score、Momentum、Confidence、Turning Point、Divergence 通過 schema/value validation。
- Historical Cycle Score 至少 24 個月，且 current score 與歷史重建最新期間對齊。
- Revision record schema 驗證。
- 單一來源失敗時保留 last-good data，不把 HTML、DNS 錯誤或欄位漂移當正式數據。

## 生成式 AI 的角色

目前**不使用生成式 AI 決定數字、趨勢或分數**。未來即使接 LLM，也只應放在已計算完成的 Facts / Signals / Scores 之上做自然語言解釋：

```text
官方資料 → 規則式 Facts / Signals / Scores → LLM 解釋
```

## 本機不是必要條件

日常使用、抓取、驗證、revision tracking、情報歷史、告警、commit 與 Pages 部署都在 GitHub 雲端完成。使用者只需要打開網頁。

---

## 三個新 Decision Scores：收尾狀態與 Definition of Done

這一階段的目標不是再增加一般圖表，而是補齊三個可以直接支援判斷的 Score：

1. **Growth Persistence Score**：這波成長能不能延續？
2. **Domestic Demand Score**：內需有沒有真的跟上？
3. **Financial Conditions Score**：資金與信用環境是在助攻還是壓制景氣？

三個 Score 都必須遵守同一套原則：

- Score 範圍固定為 **-100～+100**。
- 每個 component 都能看到 raw value、period、weight、transform 與官方來源。
- 缺值不得當成 0；只能重新正規化可用權重，並同步降低 Confidence。
- current score 與 historical reconstruction 必須使用同一套公式。
- 不同官方發布月份要做 period alignment，不得把尚未公布的資料假裝成當月資料。
- 若資料來源失敗、欄位漂移或 freshness 不足，validator 必須阻止壞資料覆蓋 last-good data。

### 1. Growth Persistence Score

目前已能計算，最近一次開發驗證約為 **+88.33**，但 Confidence 約 **65%**；代表方向可用，但資料面還沒有吃滿。

**目前已有：**

- 外銷訂單／需求訊號
- 製造業生產
- 製造業銷售
- 主要景氣／領先訊號

**還要補完：**

- [ ] 接入穩定、可自動更新的**官方詳細出口月資料**，至少能取得總出口 YoY，後續最好可拆主要商品／市場。
- [ ] 接入**庫存／存貨訊號**，用來辨識「生產跑得比終端需求快」造成的庫存累積風險。
- [ ] 將 export 與 inventory component 納入固定權重公式。
- [ ] 重建完整 Growth Persistence 歷史序列。
- [ ] current period 與歷史最新 period 必須對齊最新共同可判讀月份。
- [ ] Confidence 目標至少 **85%**；低於門檻時首頁要顯示 degraded / incomplete，而不是假裝完整。

目標分析鏈：

```text
外銷訂單 → 出口 → 生產 → 銷售 → 庫存
```

Elephant 最終應能回答：**訂單是否正在轉成出口與生產？生產是否有銷售支撐？庫存是否開始堆積？因此目前成長是否具有延續性？**

### 2. Domestic Demand Score

目前已能計算，最近一次開發驗證約為 **+45.55**，但 Confidence 約 **55%**；目前仍屬「方向性版本」，尚未達正式完成標準。

**目前已有：**

- 批發／零售／餐飲等內需活動資料
- 部分勞動市場訊號

**還要補完：**

- [ ] 接入**實質經常性薪資／實質薪資**，不要只使用名目薪資。
- [ ] 接入**製造業加班工時**或其他可代表企業勞動需求強弱的工時資料。
- [ ] 接入**就業人數／失業率／就業增減**，區分「薪資成長」與「就業量成長」。
- [ ] 視官方資料穩定度加入零售／餐飲的實質或 YoY component。
- [ ] 將薪資、就業、工時、消費 component 納入固定權重公式。
- [ ] 重建完整 Domestic Demand 歷史序列。
- [ ] Confidence 目標至少 **85%**。

目標分析鏈：

```text
就業 → 工時／加班 → 實質薪資 → 零售／餐飲 → 內需強度
```

Elephant 最終應能回答：**GDP 與出口很強時，一般家庭收入與就業是否同步改善？消費是否真的跟上？目前是外需型繁榮還是廣泛型繁榮？**

### 3. Financial Conditions Score

Financial Conditions 已完成核心資料源改造，改用中央銀行正式「金融統計月報／重要金融指標 CSV」，不再依賴 NDC 是否剛好包含金融欄位。

最近一次開發驗證約為 **+85.00，Confidence 100%**。

**目前五個元件：**

- [x] M1B 年增率
- [x] M2 年增率
- [x] 金融機構放款與投資年增率
- [x] 金融業隔夜拆款利率／短期資金價格
- [x] 股價指數／風險資產環境

**仍需最後收尾：**

- [ ] 移除為診斷央行 CSV 格式而加入的暫時 debug 輸出／workflow step。
- [ ] 確認央行 ROC 年月、英文年份與新年度首月解析都有 regression test，避免跨年再次錯掛 period。
- [ ] 確認五元件 historical reconstruction 完整、current 與 history 最新月份一致。
- [ ] 確認 Confidence 100% 時五元件都真的有有效值，不只是 weight 被錯誤視為可用。

目標分析鏈：

```text
流動性 M1B/M2 → 銀行信用 → 短期利率 → 風險資產
```

Elephant 最終應能回答：**目前金融條件是在支持實體景氣，還是開始收緊並可能拖累下一階段成長？**

## 最終首頁產品形態

首頁最終不應只顯示一個 Cycle Score，而是四層判讀：

```text
Elephant Cycle Score
現在景氣強不強？
        ↓
Growth Persistence Score
這波成長能不能延續？
        ↓
Domestic Demand Score
內需與一般家庭有沒有跟上？
        ↓
Financial Conditions Score
資金與信用環境支不支持？
```

每張卡至少顯示：

- Score（-100～+100）
- Regime / label
- Momentum
- Confidence
- Effective period
- 最重要的 2～3 個 component
- 與前月／上次造訪的變化
- 展開後完整 evidence chain
- 歷史圖與 CSV download

## 這一階段什麼時候才算完成

只有同時符合以下條件才算封版：

- [ ] Growth Persistence、Domestic Demand、Financial Conditions 三個 Score 都能由 GitHub runner 從**官方來源**自動重建。
- [ ] 三個 Score current value 均存在，且 effective period 不超前於 component 真實發布月份。
- [ ] Growth Confidence ≥ 85%。
- [ ] Domestic Demand Confidence ≥ 85%。
- [ ] Financial Conditions Confidence = 100%，或有明確且合理的官方缺值說明。
- [ ] 三個 Score 均有至少 24 個月 historical reconstruction。
- [ ] current score 與 history 最新 period/value 一致。
- [ ] validator 同時檢查 schema、值域、period alignment、freshness、component availability 與 Confidence。
- [ ] 官方來源失效時保留 last-good data 並自動開 GitHub Issue；恢復後自動關閉。
- [ ] 所有暫時 debug step / print 移除。
- [ ] Pages 首頁能直接看到四層判讀，並能 drill down 到 component、歷史與官方來源。
- [ ] Pages workflow 在正式資料更新後成功重新部署。
- [ ] 最終 GitHub-hosted runner 至少完整成功跑過一次，且沒有開啟中的自動更新 failure issue。

在以上條件完成前，不因「Score 已經能算」就把這一階段標成完成。