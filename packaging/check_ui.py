"""Exercise desktop controls without making network requests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from youtube_downloader import YouTubeDownloaderApp

app = YouTubeDownloaderApp()
errors = []
app.report_callback_exception = lambda *error: errors.append(error)
try:
    for size in ("1180x850", "1060x680"):
        app.geometry(size)
        for theme in ("Dark", "Light"):
            app._change_theme(theme)
            app.update()
            app.mode_var.set("Audio (MP3)")
            app._on_mode_change("Audio (MP3)")
            assert app.quality_var.get() == "192 kbps"
            app.mode_var.set("Video (MP4)")
            app._on_mode_change("Video (MP4)")
            assert app.quality_var.get() == "1080p"
            app.download_btn._on_enter()
            app.download_btn._on_leave()
            assert app.download_btn._canvas.find_withtag("ui_gradient")
            assert app.download_btn._canvas.find_withtag("ui_text")
            app._set_busy(True, cancellable=True)
            assert app.cancel_btn.cget("state") == "normal"
            app._set_busy(False)
            app.update()
            for widget in (app.download_btn, app.cancel_btn, app.analyze_btn, app.url_entry):
                assert widget.winfo_ismapped()
                assert widget.winfo_rootx() >= app.winfo_rootx()
                assert widget.winfo_rootx() + widget.winfo_width() <= app.winfo_rootx() + app.winfo_width(), str(widget)
                assert widget.winfo_rooty() + widget.winfo_height() <= app.winfo_rooty() + app.winfo_height(), str(widget)
    assert not errors, errors
    print("UI controls, themes, minimum window size and busy states passed")
finally:
    app.destroy()
