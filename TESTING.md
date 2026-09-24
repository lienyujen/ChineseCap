# 驗證紀錄

測試日期：2026-09-15；本機 Windows x64，Python 3.12.14，CPU 模式。

## 已驗證

- `python -m unittest discover -s tests -v`：8 項測試通過，包含繁體詞彙、獨立贅字／語意保留、毫秒進位、說話者切換與重疊、空白字幕排除、JSON 往返、非法時間軸拒絕、異常文字校正退回及網址限制。
- GUI 建構、11 段測試結果顯示、可編輯欄位與畫面檢視；畫面保存於 `test-artifacts/gui-result.png`。
- 官方 sherpa-onnx `0-four-speakers-zh.wav` 約 57 秒：指定 4 人、small INT8，完成聲紋分析與中文辨識，產出 11 段。
- 自動人數在同一範例估為 7 群，說明自動分群並不可靠。已知人數時建議手動指定。
- Qwen 1.5B 逐句校正實測：可把「軟替開發」改為「軟體開發」。仍有原始辨識錯字未能修正，不保證所有錯字與贅字都能處理。
- 曾發現多句校正的句子錯置，已改為一次只校正一個目標句，附上前後文；JSON 結構约束與文字差異檢查會拒絕異常修改。
- YouTube 公開短片 `jNQXAC9IVRw`：以 yt-dlp + Deno 成功下載 WebM 音軌，且可用 PyAV 解碼。先前 yt-dlp 測試影片 `BaW_jenozKc` 已無法使用，未用其結果判定下載功能失敗。

## 不是本次驗證的結論

未進行大量中文資料集 CER／WER、說話者 DER 評測、長達數小時錄音壓力測試、全新 Windows 虛擬機相容性或 YouTube 登入／地區限制測試。不能把單一範例視為準確率保證。

## Windows EXE 實測

- `release/ChineseCap/ChineseCap.exe --smoke-test ...`：退出碼 0，GUI、CTranslate2 4.8.2、sherpa-onnx 1.13.8 及繁體詞彙轉換通過。
- 使用同一支 EXE 的 `--batch` 模式，以打包資料夾內的模型執行上述 57 秒四人中文音訊：完整語音辨識、聲紋分析、逐句文字校正及 TXT／SRT／JSON 匯出完成，退出碼 0。結果位於 `test-artifacts/exe-full`。
- 打包過程發現建置環境的 ICU 78 DLL 被錯誤收進程式，與 Qt 所需的 Windows 原生 ICU 介面不相容。已修正成品，並加入 `scripts/fix_bundle.py` 使後续打包能重現修正。
- 成品資料夾含預設模型約 2.06 GiB，其中模型與獨立執行元件約 1.67 GiB。模型可共用或另外下載較小的 tiny／base 語音模型。

## 2026-09-24 medium 與字幕分行更新

- SRT 不再每 24 字強制切行；只在標點後換行。以 `期中考成績分析與補救教學規劃` 測試，完整名稱保留在同一行。
- 9 項核心測試全部通過，新增連續中英文專有名詞分行測試。
- 完整 faster-whisper medium 模型已下載並以 CPU INT8 實際完成 19 秒影音辨識。
- 重新打包後的 `ChineseCap.exe` 啟動測試退出碼 0；再以打包成品和內附 medium 模型跑完整影音流程，退出碼 0，TXT／SRT／JSON 均成功輸出。

## NVIDIA GPU、圖示與中性範例更新

- 新增自動、NVIDIA GPU、CPU 三種裝置模式。自動模式優先嘗試 CUDA INT8-FP16，啟動失敗會記錄原因並退回 CPU INT8；手動指定 NVIDIA 時會明確回報 CUDA 需求。
- 新增 3 項裝置選擇測試：CPU 明確選擇、自動 CUDA 失敗退回 CPU、手動 CUDA 失敗訊息；目前合計 12 項測試全部通過。
- 本機測試環境沒有可用 CUDA 裝置，因此 GPU 真機效能與 NVIDIA DLL 相容性仍需在有 NVIDIA 顯示卡且安裝 CUDA 12、cuBLAS、cuDNN 9 的電腦驗證。
- 重建後的 EXE 已在本機以 `--device auto` 完成一段影音的辨識與匯出，退出碼 0；專案資料記錄 `acceleration_requested=auto`、`asr_device=cpu`，確認無 CUDA 時能正常退回 CPU。
- 新增透明 PNG 母圖與包含 16、24、32、48、64、128、256 像素的 Windows ICO；圖示將嵌入 EXE 並用於視窗。
- 程式碼、測試與說明中的品牌範例已移除，改為公司會議、課程、考試與教學內容。
