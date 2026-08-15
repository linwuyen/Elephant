# Decision Scores

Elephant 的首頁核心不是單一總分，而是四層診斷：

1. **Cycle Score**：現在景氣強不強？
2. **Growth Persistence Score**：這波景氣還能持續嗎？
3. **Domestic Demand Score**：台灣一般人的經濟真的有變好嗎？
4. **Financial Conditions Score**：資金環境是在支持還是壓制景氣？

三個 Decision Score 都是 deterministic、可追溯、可歷史重建的 -100～+100 規則式分數。缺值不當成 0，只對可用元件重新正規化權重，並以 Confidence 顯示資料覆蓋程度。

## Growth Persistence

分析鏈：

`外銷訂單 → 出口 → 生產 → 銷售 → 庫存`

固定權重：

- 外銷訂單 30%
- 海關出口 20%
- 製造業生產 20%
- 製造業銷售 15%
- 存貨壓力 15%

用途不是判斷「目前很強」，而是檢查訂單是否真的轉成出口與生產、生產是否有銷售支撐，以及庫存是否開始堆積。

庫存優先使用經濟部統計處官方「製造業存貨量指數－按四大行業別分」中的製造業總體序列。source parser 同時接受官方 long-form 與防禦性的 wide/transposed export layout，但三種 layout 都必須解析到同一個 **製造業存貨量指數**；不得改用房市庫存、存貨率或其他不同概念來補 coverage。

## Domestic Demand

分析鏈：

`實質薪資 → 就業 → 零售 → 餐飲 → 信用卡消費`

固定權重：

- 實質薪資 25%
- 就業 20%
- 零售 20%
- 餐飲 15%
- 信用卡消費 20%

信用卡資料使用金管會銀行局公開、由聯合信用卡處理中心提供的月資料。它只涵蓋聯卡中心處理的信用卡消費交易，因此在 Elephant 中明確視為 **consumer-spending proxy**，不是所有民間消費或所有支付行為。

為降低通膨把名目消費放大的問題，信用卡 component 優先使用「簽帳金額 YoY - CPI YoY」；實質薪資則使用薪資 YoY - CPI YoY。

薪資與就業的 primary source 是主計總處（DGBAS）官方 XML：工業及服務業每人每月總薪資、工業及服務業受僱員工人數。若 `ws.dgbas.gov.tw` 的 XML transport 因憑證鏈或上游連線問題不可用，supplement 只允許 fallback 到 **`www.dgbas.gov.tw` 官方「薪資與生產力統計」月報標題**，抽取同一月份的「工業及服務業受僱員工人數」與「本月總薪資平均」。這是同一官方、同一指標語義的 alternate publication path，不得替換成失業率、總就業人口或其他 proxy。TLS verification 始終開啟，禁止 `-k` / `verify=False`。

## Financial Conditions

分析鏈：

`M1B → M2 → 銀行信用 → 利率 → 匯率`

固定權重：

- M1B 25%
- M2 20%
- 金融機構放款與投資 25%
- 短期利率 15%
- 匯率 15%

金融資料直接使用中央銀行金融統計月報。匯率 component 暫以 USD/TWD 12 個月變動作透明 proxy：在台灣出口導向的金融條件框架下，新台幣適度貶值視為較寬鬆；這是 Elephant 的模型假設，不是普遍經濟定律，極端匯率波動仍應另視為風險。

## Score contract

三個 Score 都必須遵守：

- 範圍固定 -100～+100。
- component 必須保存 raw value、period、weight、transform note、source。
- current 與 historical reconstruction 必須使用同一套公式。
- 不同官方發布時差用 period alignment 處理，不得把尚未公布的資料掛到最新月份。
- 缺值只能重新正規化可用權重並降低 Confidence，不得補 0。
- validator 會鎖住固定 component set，避免模型定義在未察覺下漂移。
- 原始資料下載失敗時保留 last-good；不得讓 HTML、欄位漂移或錯 period 覆蓋健康資料。
- alternate publication path 必須保持 **同一提供機關、同一指標定義、同一頻率/期間語義**；不符合者只能降 Confidence，不能當 fallback。

## 下一層

完成這三個核心後，Elephant 的下一個兩層診斷是：

### AI Concentration

回答：**台灣現在到底多依賴 AI？**

預計分析鏈：

`電子訂單 × 電子出口 × 電子生產 × 非電子 breadth`

### Housing / Regional Vitality

回答：**哪些城市真的在變強？**

預計分析鏈：

`人口 × 信用卡 × 新設公司 × 房市成交 × 房價 × 用電`

目標不是做更多圖表，而是讓 Elephant 最終成為台灣經濟的多層次診斷系統。
