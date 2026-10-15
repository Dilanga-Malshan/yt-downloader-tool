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
            app._apply_video_info(
                {"title": "A long video title showing how controls remain visible in the compact layout " * 3,
                 "uploader": "A channel with a very long display name", "duration": 300, "view_count": 2000},
                ["Best", "2160p (4K)", "1440p", "1080p", "720p"], None,
            )
            app.update()
            for widget in (app.open_folder_btn, app.resolution_label):
                panel = widget.master if widget is app.resolution_label else widget.master.master
                assert widget.winfo_rooty() + widget.winfo_height() <= panel.winfo_rooty() + panel.winfo_height(), "Panel clips a control"
            for widget in (app.download_btn, app.cancel_btn, app.analyze_btn, app.url_entry,
                           app.mode_selector, app.quality_menu, app.folder_entry,
                           app.choose_folder_btn, app.open_folder_btn,
                           app.thumbnail_frame, app.title_label, app.resolution_label):
                assert widget.winfo_ismapped()
                assert widget.winfo_rootx() >= app.winfo_rootx()
                assert widget.winfo_rootx() + widget.winfo_width() <= app.winfo_rootx() + app.winfo_width(), str(widget)
                assert widget.winfo_rooty() + widget.winfo_height() <= app.winfo_rooty() + app.winfo_height(), str(widget)
    assert not errors, errors
    print("UI controls, themes, minimum window size and busy states passed")
finally:
    app.destroy()
