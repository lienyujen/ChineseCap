from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QComboBox, QSpinBox, QCheckBox, QProgressBar,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox)

from .core import export, load_project, stamp
from .models import Cancelled, default_root, install
from .pipeline import Options, cuda_available, run


class Worker(QThread):
    log = Signal(str)
    progress = Signal(int)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, function):
        super().__init__()
        self.function = function
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.function(self.log.emit, self.progress.emit, self.cancel))
        except Cancelled:
            self.failed.emit('已取消；沒有覆寫先前結果。')
        except Exception as error:
            self.failed.emit(f'{type(error).__name__}：{error}')


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ChineseCap｜本機中文逐字稿')
        icon = Path(__file__).resolve().parent.parent / 'assets' / 'ChineseCap.ico'
        if getattr(sys, 'frozen', False):
            packaged = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
            adjacent = Path(sys.executable).parent
            icon = packaged / 'ChineseCap.png' if sys.platform == 'darwin' else adjacent / 'ChineseCap.ico'
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1180, 850)
        self.cues, self.metadata = [], {}
        self.worker = None
        host = QWidget()
        self.setCentralWidget(host)
        layout = QVBoxLayout(host)
        title = QLabel('ChineseCap   本機中文逐字稿')
        title.setStyleSheet('font-size:24px; font-weight:700; color:#134e4a; padding:8px 0;')
        layout.addWidget(title)
        layout.addWidget(QLabel('影音轉文字 · 台灣繁體 · 多人聲紋 · 上下文校正｜模型準備完成後，本機檔案可離線處理'))
        self.settings = QGroupBox('輸入與模型')
        settings = QVBoxLayout(self.settings)
        layout.addWidget(self.settings)
        row = QHBoxLayout()
        self.source = QLineEdit()
        self.source.setPlaceholderText('選擇 MP4 / MP3 / WAV / M4A 等影音，或貼上 YouTube 影片網址')
        row.addWidget(self.source, 1)
        choose = QPushButton('選擇影音')
        choose.clicked.connect(self.choose_source)
        row.addWidget(choose)
        settings.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel('語音模型'))
        self.asr = QComboBox()
        for label, value in [('medium｜中文較準／模型較大', 'medium'), ('small｜中文平衡', 'small'),
                             ('base｜較小', 'base'), ('tiny｜最小／中文較弱', 'tiny')]:
            self.asr.addItem(label, value)
        row.addWidget(self.asr)
        row.addWidget(QLabel('運算裝置'))
        self.acceleration = QComboBox()
        self.acceleration.addItem('自動｜優先 NVIDIA，失敗退回 CPU', 'auto')
        self.acceleration.addItem('NVIDIA GPU｜CUDA', 'cuda')
        self.acceleration.addItem('CPU', 'cpu')
        row.addWidget(self.acceleration)
        self.diar = QCheckBox('區分說話者')
        self.diar.setChecked(True)
        row.addWidget(self.diar)
        row.addWidget(QLabel('人數（0＝自動）'))
        self.speakers = QSpinBox()
        self.speakers.setRange(0, 20)
        row.addWidget(self.speakers)
        self.correction = QCheckBox('上下文清理／改錯')
        self.correction.setChecked(True)
        row.addWidget(self.correction)
        row.addWidget(QLabel('CPU 執行緒'))
        self.threads = QSpinBox()
        self.threads.setRange(1, max(2, os.cpu_count() or 4))
        self.threads.setValue(min(4, os.cpu_count() or 4))
        row.addWidget(self.threads)
        row.addStretch()
        settings.addLayout(row)
        row = QHBoxLayout()
        self.model_root = QLineEdit(str(default_root()))
        row.addWidget(QLabel('模型資料夾'))
        row.addWidget(self.model_root)
        choose_models = QPushButton('變更')
        choose_models.clicked.connect(self.choose_models)
        row.addWidget(choose_models)
        self.prepare = QPushButton('下載／準備模型')
        self.prepare.clicked.connect(self.prepare_models)
        row.addWidget(self.prepare)
        settings.addLayout(row)
        self.glossary = QLineEdit()
        self.glossary.setPlaceholderText('選填：人名、課程與專有名詞，例如：年度預算、期中考、牛頓第二運動定律')
        settings.addWidget(self.glossary)
        row = QHBoxLayout()
        self.start = QPushButton('開始轉錄')
        self.start.setStyleSheet('background:#0f766e;color:white;padding:10px 24px;font-weight:bold;')
        self.start.clicked.connect(self.start_run)
        row.addWidget(self.start)
        self.cancel_button = QPushButton('取消')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_job)
        row.addWidget(self.cancel_button)
        self.progress = QProgressBar()
        row.addWidget(self.progress, 1)
        layout.addLayout(row)
        layout.addWidget(QLabel('核對結果：雙擊「說話者」或「清理後文字」可修改；清空文字可排除該段。原始辨識保留供比對。'))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['開始', '結束', '說話者', '原始辨識', '清理後文字', '檢查提示'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 105)
        self.table.setColumnWidth(1, 105)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 260)
        self.table.setColumnWidth(4, 300)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.open_project = QPushButton('開啟專案 JSON')
        self.open_project.clicked.connect(self.open_saved)
        row.addWidget(self.open_project)
        self.srt_speaker = QCheckBox('SRT 顯示說話者')
        self.srt_speaker.setChecked(True)
        row.addWidget(self.srt_speaker)
        self.save = QPushButton('匯出 TXT ＋ SRT ＋ 專案')
        self.save.setEnabled(False)
        self.save.clicked.connect(self.save_result)
        row.addWidget(self.save)
        row.addStretch()
        layout.addLayout(row)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(110)
        self.logs.setMaximumBlockCount(300)
        layout.addWidget(self.logs)
        gpu_status = '偵測到 NVIDIA CUDA 裝置，將優先使用 GPU。' if cuda_available() else '目前未偵測到可用的 NVIDIA CUDA 裝置，自動模式將使用 CPU。'
        self.logs.appendPlainText('成品已附 medium 完整模型，中文準確度優先建議使用 medium。' + gpu_status)

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, '選擇影音', '', '影音檔 (*.mp4 *.mkv *.webm *.mov *.mp3 *.wav *.m4a *.flac *.aac *.ogg);;所有檔案 (*)')
        if path:
            self.source.setText(path)

    def choose_models(self):
        path = QFileDialog.getExistingDirectory(self, '模型資料夾', self.model_root.text())
        if path:
            self.model_root.setText(path)

    def options(self):
        return Options(self.source.text().strip(), Path(self.model_root.text().strip()),
            self.asr.currentData(), self.diar.isChecked(), self.speakers.value(),
            self.correction.isChecked(), self.threads.value(), self.glossary.text(),
            self.acceleration.currentData())

    def launch(self, function):
        self.settings.setEnabled(False)
        self.start.setEnabled(False)
        self.open_project.setEnabled(False)
        self.save.setEnabled(False)
        self.table.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.worker = Worker(function)
        self.worker.log.connect(self.logs.appendPlainText)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.result.connect(self.received)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def prepare_models(self):
        opt = self.options()
        self.launch(lambda log, progress, cancel: install(opt.root, opt.asr, opt.diarize, opt.correction, log, cancel))

    def start_run(self):
        if not self.source.text().strip():
            QMessageBox.information(self, '需要影音', '請先選擇影音檔案或貼上 YouTube 網址。')
            return
        opt = self.options()
        self.launch(lambda log, progress, cancel: run(opt, log, progress, cancel))

    def cancel_job(self):
        if self.worker:
            self.worker.cancel.set()
            self.logs.appendPlainText('正在取消，會在目前模型運算／下載請求完成後停止…')
            self.cancel_button.setEnabled(False)

    def received(self, result):
        if result is not None:
            self.cues, self.metadata = result
            self.populate()
            self.logs.appendPlainText(f'已完成 {len(self.cues)} 段，可核對後匯出。')

    def failed(self, error):
        self.logs.appendPlainText(error)
        if not error.startswith('已取消'):
            QMessageBox.warning(self, '處理未完成', error)

    def finished(self):
        self.settings.setEnabled(True)
        self.start.setEnabled(True)
        self.open_project.setEnabled(True)
        self.table.setEnabled(True)
        self.save.setEnabled(bool(self.cues))
        self.cancel_button.setEnabled(False)

    def populate(self):
        self.table.setRowCount(len(self.cues))
        for row, cue in enumerate(self.cues):
            for col, value in enumerate([stamp(cue.start), stamp(cue.end), cue.speaker,
                                        cue.raw, cue.text, '；'.join(cue.notes)]):
                item = QTableWidgetItem(value)
                if col not in (2, 4):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
        self.save.setEnabled(bool(self.cues))

    def open_saved(self):
        path, _ = QFileDialog.getOpenFileName(self, '開啟專案', '', 'ChineseCap 專案 (*.json)')
        if path:
            try:
                self.cues, self.metadata = load_project(Path(path))
                self.populate()
            except Exception as e:
                QMessageBox.warning(self, '開啟失敗', str(e))

    def save_result(self):
        path = QFileDialog.getExistingDirectory(self, '選擇匯出位置')
        if not path:
            return
        try:
            for row, cue in enumerate(self.cues):
                speaker = self.table.item(row, 2).text().strip() or '未辨識'
                text = self.table.item(row, 4).text().strip()
                if text != cue.text or speaker != cue.speaker:
                    if '使用者已修改' not in cue.notes:
                        cue.notes.append('使用者已修改')
                cue.speaker, cue.text = speaker, text
            target = export(self.cues, Path(path), 'ChineseCap', self.metadata, self.srt_speaker.isChecked())
            self.logs.appendPlainText(f'已匯出：{target}')
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except Exception as e:
            QMessageBox.warning(self, '匯出失敗', str(e))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_job()
            QMessageBox.information(self, '正在停止', '請等目前運算停止後再關閉視窗。')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication([])
    app.setStyle('Fusion')
    app.setStyleSheet('QWidget {font-family:"Microsoft JhengHei UI";font-size:13px;} QLineEdit,QComboBox,QSpinBox{padding:5px;} QGroupBox{margin-top:8px;padding-top:12px;} QPushButton{padding:6px 12px;}')
    window = Window()
    window.show()
    return app.exec()
