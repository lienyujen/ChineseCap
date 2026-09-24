import sys


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    if '--batch' in sys.argv:
        from chinesecap.cli import main
        sys.exit(main())
    elif '--smoke-test' in sys.argv:
        import json
        from pathlib import Path
        import av, ctranslate2, sherpa_onnx, yt_dlp
        from PySide6.QtWidgets import QApplication
        from chinesecap.gui import Window
        from chinesecap.core import clean_text
        app = QApplication([])
        window = Window()
        assert clean_text('软件') == '軟體'
        result = {'status': 'ok', 'gui': True, 'asr': ctranslate2.__version__,
                  'speaker': sherpa_onnx.__version__, 'traditional': clean_text('软件')}
        dest = Path(sys.argv[sys.argv.index('--smoke-test')+1])
        dest.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        window.close()
    else:
        from chinesecap.gui import main
        sys.exit(main())
