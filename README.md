# ChineseCap｜本機中文逐字稿

Windows x64 與 macOS 桌面程式。將中文影音或單支 YouTube 影片轉成台灣繁體中文清理稿與 SRT，支援多人說話者標記、贅字清理及上下文校正。
支援 NVIDIA GPU 自動偵測；GPU 環境不可用時會安全退回 CPU。

## 使用

1. Windows：解壓 ZIP 後開啟 `ChineseCap.exe`，並保留整個資料夾。macOS：依處理器下載 Apple Silicon 或 Intel DMG，將 ChineseCap 拖入 Applications。
2. 第一次使用選擇模型後，按「下載／準備模型」。如果已有模型，將模型資料夾指向專案的 `models`。模型不包入 EXE，可更新、攜帶及重複使用。
3. 選擇影音檔或貼上 YouTube 網址。選填專有名詞；已知發言人數可填 2、3…，0 為自動估計。
4. 按「開始轉錄」。完成後可雙擊說話者或清理後文字修改。清空文字會排除該段字幕，原始辨識仍保留。
5. 按「匯出 TXT ＋ SRT ＋ 專案」，選資料夾。每次建立新資料夾，不覆蓋前次結果。

輸出包含：台灣繁體 `逐字稿.txt`、`原始辨識.txt`、YouTube 可匯入的 UTF-8 `字幕.srt`、保存時間軸、原文、校正稿、提示的 `專案.json`。可重新開啟 JSON 繼續編輯。SRT 可選是否顯示說話者。

## 模型與資源

| 功能 | 使用模型／引擎 | 說明 |
| --- | --- | --- |
| 語音 | faster-whisper，CPU INT8 | medium 為預設且中文較準；small、base、tiny 依序減少容量與運算量 |
| 多人分辨 | sherpa-onnx + pyannote segmentation 3.0 + 中文 3D-Speaker embedding | 依聲紋分群，按照首次出現編為說話者 1、2、3… |
| 上下文校正 | Qwen2.5-1.5B-Instruct Q4_K_M + llama.cpp CPU | 約 1 GB 的小型文字模型，連同相鄰句子、專有名詞清理校正 |
| 台灣繁體 | OpenCC s2twp | 字形與常見詞彙轉換；不等於所有語意均已校正 |

公開安裝包不內含大型模型；首次開啟後選擇模型並按「下載／準備模型」。中文準確度優先請使用 medium；一般 CPU 速度會比 small 慢，建議 16 GB RAM。small 適合速度與容量優先；tiny 不保證足以辨識複雜中文。模型分階段載入，降低同時佔用。音訊目前整段解碼於 RAM；16 kHz float32 約每小時 230 MB，聲紋演算還會額外使用記憶體。

NVIDIA 模式使用 CUDA INT8-FP16 加速 Whisper。需要相容的 NVIDIA 驅動程式、CUDA 12、cuBLAS 與 cuDNN 9。選「自動」時若 GPU 或執行庫不可用會退回 CPU；選「NVIDIA GPU」時會顯示明確錯誤。聲紋分析與文字校正目前仍使用 CPU。

## 辨識範圍與限制

- 處理影音的「音軌」，不分析畫面字幕、人物臉部或唇形。
- 聲紋分群不是身分認證，無法自動知道真名。聲音相近、噪音或短發言可能分錯；可修改標籤。模型輸出重疊區間時會標記待核對，也可能漏判；本版沒有重疊人聲分離模型。
- 清理稿不是法律意義的逐字原稿。模型嘗試刪除無語意贅字，不保證刪得完全或完全不改變語意。阿拉伯數字變動、大幅刪除、文字差異過大及格式異常會退回基礎清理稿；仍需核對中文數字、人名、同音字、否定詞及專業內容。
- 校正使用相鄰句子上下文，沒有把整部長影片一次塞入文字模型。保留原始時間軸；修改文字不會重新對齊音素。字幕以最多約 6 秒／36 字分段；SRT 只在標點後換行，不會依固定字數切斷連續名詞。單字時間戳與說話者邊界是模型估計。
- 支援多人輪流發言；不宣稱自動估計人數一定正確。已知人數時手動指定通常較可控。
- 取消會等到目前模型呼叫或下載請求的安全停止點，未必立即停止。

## 網路與本機運算

模型首次下載會連到 Hugging Face 與 GitHub；YouTube 匯入必須連網。模型備齊後，本機檔案辨識與文字校正不需要雲端服務；音訊與逐字稿不會送到雲端 AI。文字引擎只監聽 `127.0.0.1`，使用每次隨機金鑰，工作結束即停止。

YouTube 因登入、地區、存取權或網站變更可能無法下載；本版不處理直播，也不自動讀取瀏覽器登入 Cookie。可改匯入已取得的本機影音。PyAV 內含影音解碼所需元件，不需另外安裝 FFmpeg CLI。

YouTube JavaScript 支援採官方 Deno 2.9.6 與 yt-dlp-ejs，準備模型時一併下載符合 Windows、macOS Apple Silicon 或 macOS Intel 的 Deno 並驗證 SHA-256。

macOS 公開版採 ad-hoc 簽署，未經 Apple 公證。第一次開啟若被 Gatekeeper 阻擋，請在 Finder 對 ChineseCap 按右鍵選「打開」，再確認一次。模型預設存於 `~/Library/Application Support/ChineseCap/models`。

## 開發與打包

需要 Python 3.12。Windows 使用 PowerShell；macOS 使用 `./build-macos.sh`：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\build.ps1
.\.venv\Scripts\python.exe scripts/copy_models.py
```

打包為資料夾式 EXE，包含 Python 與依賴；目標電腦不用安裝 Python。模型另存，可將 `models` 資料夾複製到 EXE 旁供離線攜帶。執行檔尚未做商用數位簽章。

本機文字引擎採用固定 llama.cpp b10964 CPU 發行檔，下載驗證 SHA-256；模型來源與授權見 `THIRD_PARTY.md`。

批次處理（結果與進度寫入輸出資料夾的 result.json / batch.log）：

```powershell
.\release\ChineseCap\ChineseCap.exe --batch "C:\影音\會議.mp4" --models ".\release\ChineseCap\models" --output ".\output" --speakers 2 --device auto
```
