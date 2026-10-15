import io
import os
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import customtkinter as ctk
import yt_dlp
from PIL import Image


# PyInstaller stores bundled binaries in _MEIPASS (the _internal folder).
if getattr(sys, "frozen", False):
    bundle_dir = str(Path(sys._MEIPASS))
    os.environ["PATH"] = bundle_dir + os.pathsep + os.environ.get("PATH", "")


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_ICON = RESOURCE_DIR / "assets" / "app-icon.ico"

APP_TITLE = "YT Downloader Pro"
APP_SIZE = "1180x850"
DEFAULT_DIR = str(Path.home() / "Downloads")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DownloadCancelled(Exception):
    pass


def is_valid_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower().split(":")[0]
        return parsed.scheme in {"http", "https"} and (
            host == "youtu.be"
            or host == "youtube.com"
            or host.endswith(".youtube.com")
        )
    except Exception:
        return False


def format_duration(seconds) -> str:
    if not seconds:
        return "Unknown duration"

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def compact_number(value) -> str:
    if value is None:
        return "—"

    number = float(value)
    for suffix, limit in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if number >= limit:
            return f"{number / limit:.1f}{suffix}"
    return f"{int(number):,}"


class YouTubeDownloaderApp(ctk.CTk):
    VIDEO_DEFAULTS = ["Best", "2160p (4K)", "1440p", "1080p", "720p", "480p", "360p"]
    AUDIO_BITRATES = ["320 kbps", "256 kbps", "192 kbps", "128 kbps"]

    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        if sys.platform == "win32":
            # CustomTkinter schedules its default icon after startup.
            self.after(250, lambda: self.iconbitmap(str(APP_ICON)))
        width = min(1180, max(1060, self.winfo_screenwidth() - 80))
        height = min(850, max(680, self.winfo_screenheight() - 100))
        self.geometry(f"{width}x{height}")
        self.minsize(1060, 680)

        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value=DEFAULT_DIR)
        self.mode_var = tk.StringVar(value="Video (MP4)")
        self.quality_var = tk.StringVar(value="1080p")
        self.theme_var = tk.StringVar(value="Dark")
        self.status_var = tk.StringVar(value="Ready")
        self.detail_var = tk.StringVar(value="Paste a YouTube link and click Analyze.")
        self.progress_var = tk.DoubleVar(value=0)

        self.cancel_requested = False
        self.thumbnail_image = None
        self.current_info = None
        self.video_quality_values = list(self.VIDEO_DEFAULTS)

        self._build_ui()
        self._refresh_ffmpeg_status()

    def _build_ui(self):
        bg = ("#f3f5fa", "#0b0e14")
        surface = ("#ffffff", "#141923")
        inset = ("#edf0f6", "#0e131c")
        border = ("#e0e5ee", "#252d3c")
        ink = ("#172033", "#f2f5fc")
        muted = ("#637086", "#95a1b5")
        accent, hover = "#ef233c", "#cc1830"
        self.configure(fg_color=bg)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        def label(parent, text, size=13, bold=False, color=ink, **kwargs):
            return ctk.CTkLabel(parent, text=text, text_color=color,
                                font=ctk.CTkFont(family="Segoe UI", size=size,
                                                weight="bold" if bold else "normal"), **kwargs)

        def button(parent, text, command, primary=False, **kwargs):
            return ctk.CTkButton(parent, text=text, command=command, height=42,
                                corner_radius=10, fg_color=accent if primary else inset,
                                hover_color=hover if primary else border,
                                text_color="white" if primary else ink,
                                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                **kwargs)

        sidebar = ctk.CTkFrame(self, width=184, corner_radius=0, fg_color=surface)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(5, weight=1)
        self.brand_image = ctk.CTkImage(Image.open(RESOURCE_DIR / "assets" / "app-icon.png"), size=(48, 48))
        ctk.CTkLabel(sidebar, text="", image=self.brand_image).grid(row=0, column=0, sticky="w", padx=22, pady=(28, 12))
        label(sidebar, "YT Downloader", 18, True).grid(row=1, column=0, sticky="w", padx=22)
        label(sidebar, "P R O  /  D E S K T O P", 10, color=muted).grid(row=2, column=0, sticky="w", padx=22, pady=(0, 36))
        label(sidebar, "   Download studio", 13, True, color="white", fg_color=accent,
              corner_radius=10, height=44, anchor="w").grid(row=3, column=0, sticky="ew", padx=14)
        button(sidebar, "Open downloads", self.open_output_folder).grid(row=4, column=0, sticky="ew", padx=14, pady=10)
        label(sidebar, "APPEARANCE", 10, True, muted).grid(row=6, column=0, sticky="w", padx=22, pady=(10, 8))
        self.theme_menu = ctk.CTkOptionMenu(sidebar, values=["Dark", "Light", "System"],
                                          variable=self.theme_var, command=self._change_theme,
                                          fg_color=inset, button_color=border, button_hover_color=accent,
                                          text_color=ink, dropdown_fg_color=surface, dropdown_text_color=ink,
                                          corner_radius=9, height=36, width=140)
        self.theme_menu.grid(row=7, column=0, padx=18, pady=(0, 18))
        label(sidebar, "Made by Dilanga Malshan", 10, color=muted).grid(row=8, column=0, padx=12, pady=(0, 20))

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        heading = ctk.CTkFrame(main, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        heading.grid_columnconfigure(0, weight=1)
        label(heading, "Your next download.", 29, True).grid(row=0, column=0, sticky="w")
        label(heading, "One link. Your favorite quality. Saved locally.", 13, color=muted).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.ffmpeg_badge = label(heading, "Checking FFmpeg…", 11, corner_radius=8, padx=12, height=30)
        self.ffmpeg_badge.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))

        link_card = ctk.CTkFrame(main, fg_color=surface, corner_radius=16, border_width=1, border_color=border)
        link_card.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        link_card.grid_columnconfigure(0, weight=1)
        label(link_card, "01  /  ADD YOUR LINK", 11, True, muted).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))
        url_row = ctk.CTkFrame(link_card, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        url_row.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(url_row, textvariable=self.url_var, height=46,
                                     placeholder_text="Paste a YouTube video link here…",
                                     fg_color=inset, border_color=border, corner_radius=10, text_color=ink)
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<Return>", lambda event: self.start_analyze() if self.analyze_btn.cget("state") == "normal" else None)
        button(url_row, "Paste", self._paste_url, width=68).grid(row=0, column=1, padx=8)
        self.analyze_btn = button(url_row, "Analyze link", self.start_analyze, primary=True, width=112)
        self.analyze_btn.grid(row=0, column=2)

        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1, uniform="panels")
        content.grid_columnconfigure(1, weight=1, uniform="panels")
        content.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(content, fg_color=surface, corner_radius=16,
                                     border_width=1, border_color=border)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        left.grid_columnconfigure(0, weight=1)
        right = ctk.CTkScrollableFrame(content, fg_color=surface, corner_radius=16,
                                      border_width=1, border_color=border)
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        right.grid_columnconfigure(0, weight=1)

        label(left, "02  /  MAKE IT YOURS", 11, True, muted).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        label(left, "Download settings", 20, True).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 18))
        label(left, "Format", 13, True).grid(row=2, column=0, sticky="w", padx=16)
        self.mode_selector = ctk.CTkSegmentedButton(left, values=["Video (MP4)", "Audio (MP3)"],
                                                   variable=self.mode_var, command=self._on_mode_change,
                                                   height=42, corner_radius=9, fg_color=inset,
                                                   selected_color=accent, selected_hover_color=hover,
                                                   unselected_color=inset, unselected_hover_color=border,
                                                   text_color=ink)
        self.mode_selector.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 18))
        self.quality_label = label(left, "Video quality", 13, True)
        self.quality_label.grid(row=4, column=0, sticky="w", padx=16)
        self.quality_menu = ctk.CTkOptionMenu(left, values=self.video_quality_values,
                                             variable=self.quality_var, height=42,
                                             fg_color=inset, button_color=border, button_hover_color=accent,
                                             text_color=ink, dropdown_fg_color=surface, dropdown_text_color=ink,
                                             corner_radius=9)
        self.quality_menu.grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 18))
        label(left, "Save location", 13, True).grid(row=6, column=0, sticky="w", padx=16)
        self.folder_entry = ctk.CTkEntry(left, textvariable=self.output_var, height=40,
                                        fg_color=inset, border_color=border, text_color=ink, corner_radius=9)
        self.folder_entry.grid(row=7, column=0, sticky="ew", padx=16, pady=(8, 8))
        folder_actions = ctk.CTkFrame(left, fg_color="transparent")
        folder_actions.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 18))
        folder_actions.grid_columnconfigure((0, 1), weight=1)
        button(folder_actions, "Change folder", self.choose_folder, width=100).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.open_folder_btn = button(folder_actions, "Open folder", self.open_output_folder, width=90)
        self.open_folder_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        label(right, "03  /  VIDEO PREVIEW", 11, True, muted).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 12))
        self.thumbnail_frame = ctk.CTkFrame(right, height=170, fg_color=inset, corner_radius=12)
        self.thumbnail_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.thumbnail_frame.grid_propagate(False)
        self.thumbnail_frame.grid_columnconfigure(0, weight=1)
        self.thumbnail_frame.grid_rowconfigure(0, weight=1)
        self.thumbnail_label = label(self.thumbnail_frame, "▶\nYour video, right here.\nAnalyze a link to see the details.", 14, color=muted)
        self.thumbnail_label.grid(row=0, column=0, sticky="nsew")
        self.title_label = label(right, "Ready when you are", 19, True, wraplength=290, justify="left", anchor="w")
        self.title_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        for row, name, text in [(3, "channel_label", "Channel: —"), (4, "duration_label", "Duration: —"),
                                (5, "views_label", "Views: —"), (6, "resolution_label", "Available quality: —")]:
            widget = label(right, text, 12, color=muted, anchor="w", wraplength=290, justify="left")
            widget.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 6 if row < 6 else 18))
            setattr(self, name, widget)

        transfer = ctk.CTkFrame(main, fg_color=surface, corner_radius=16, border_width=1, border_color=border)
        transfer.grid(row=3, column=0, sticky="ew", pady=(18, 0))
        transfer.grid_columnconfigure(0, weight=1)
        status_row = ctk.CTkFrame(transfer, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 5))
        status_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(status_row, textvariable=self.status_var, text_color=ink,
                     font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        self.percent_label = label(status_row, "0%", 14, True, accent)
        self.percent_label.grid(row=0, column=1)
        self.progress_bar = ctk.CTkProgressBar(transfer, height=6, fg_color=inset, progress_color=accent, corner_radius=3)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(transfer, textvariable=self.detail_var, anchor="w", text_color=muted,
                     wraplength=370, justify="left", font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))
        actions = ctk.CTkFrame(transfer, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=3, padx=(0, 20), pady=16)
        self.cancel_btn = button(actions, "Cancel", self.cancel_download, width=70, state="disabled")
        self.cancel_btn.pack(side="left", padx=(0, 8))
        self.download_btn = button(actions, "Start download", self.start_download, primary=True, width=148)
        self.download_btn.pack(side="left")
        label(main, "Download only media you own or have permission to save.", 10, color=muted).grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.url_entry.focus()

    def _change_theme(self, value):
        ctk.set_appearance_mode(value.lower())

    def _refresh_ffmpeg_status(self):
        if shutil.which("ffmpeg"):
            self.ffmpeg_badge.configure(
                text="FFmpeg  Ready",
                fg_color=("#d7f5df", "#143d24"),
                text_color=("#176b32", "#83e39f"),
            )
        else:
            self.ffmpeg_badge.configure(
                text="FFmpeg  Missing",
                fg_color=("#ffe3e3", "#4a1d1d"),
                text_color=("#a62a2a", "#ff9a9a"),
            )

    def _paste_url(self):
        try:
            value = self.clipboard_get().strip()
        except tk.TclError:
            return

        self.url_var.set(value)

    def _on_mode_change(self, mode):
        if mode == "Audio (MP3)":
            self.quality_label.configure(text="Audio bitrate")
            self.quality_menu.configure(values=self.AUDIO_BITRATES)
            self.quality_var.set("192 kbps")
        else:
            self.quality_label.configure(text="Video quality")
            self.quality_menu.configure(values=self.video_quality_values)
            preferred = "1080p"
            self.quality_var.set(
                preferred if preferred in self.video_quality_values else self.video_quality_values[0]
            )

    def choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.output_var.get() or DEFAULT_DIR)
        if selected:
            self.output_var.set(selected)

    def open_output_folder(self):
        folder = self.output_var.get().strip() or DEFAULT_DIR
        os.makedirs(folder, exist_ok=True)

        try:
            os.startfile(folder)
        except AttributeError:
            messagebox.showinfo("Folder", folder)
        except OSError as exc:
            messagebox.showerror("Open folder failed", str(exc))

    def _set_busy(self, busy: bool, cancellable: bool = False):
        normal_state = "disabled" if busy else "normal"
        self.download_btn.configure(state=normal_state)
        self.analyze_btn.configure(state=normal_state)
        self.cancel_btn.configure(state="normal" if cancellable else "disabled")

    def start_analyze(self):
        url = self.url_var.get().strip()

        if not is_valid_youtube_url(url):
            messagebox.showerror("Invalid URL", "Please enter a valid YouTube URL.")
            return

        self.status_var.set("Analyzing video...")
        self.detail_var.set("Reading video information and available formats.")
        self.progress_bar.set(0)
        self.percent_label.configure(text="0%")
        self._set_busy(True)

        threading.Thread(target=self._analyze_worker, args=(url,), daemon=True).start()

    def _analyze_worker(self, url):
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            heights = sorted(
                {
                    int(fmt["height"])
                    for fmt in info.get("formats", [])
                    if fmt.get("height")
                },
                reverse=True,
            )

            quality_values = ["Best"]
            labels = {
                2160: "2160p (4K)",
                1440: "1440p",
                1080: "1080p",
                720: "720p",
                480: "480p",
                360: "360p",
            }

            for height, label in labels.items():
                if any(h >= height for h in heights):
                    quality_values.append(label)

            if len(quality_values) == 1:
                quality_values = list(self.VIDEO_DEFAULTS)

            thumbnail_bytes = None
            thumbnail_url = info.get("thumbnail")
            if thumbnail_url:
                try:
                    request = Request(
                        thumbnail_url,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    with urlopen(request, timeout=10) as response:
                        thumbnail_bytes = response.read()
                except Exception:
                    thumbnail_bytes = None

            self.after(
                0,
                lambda: self._apply_video_info(info, quality_values, thumbnail_bytes),
            )
        except Exception as exc:
            error_text = str(exc)
            self.after(0, lambda e=error_text: self._show_error("Analyze failed", e))
        finally:
            self.after(0, lambda: self._set_busy(False))

    def _apply_video_info(self, info, quality_values, thumbnail_bytes):
        self.current_info = info
        self.video_quality_values = quality_values

        if self.mode_var.get() == "Video (MP4)":
            self.quality_menu.configure(values=quality_values)
            if "1080p" in quality_values:
                self.quality_var.set("1080p")
            elif len(quality_values) > 1:
                self.quality_var.set(quality_values[1])
            else:
                self.quality_var.set(quality_values[0])

        title = info.get("title") or "Untitled video"
        uploader = info.get("uploader") or info.get("channel") or "Unknown"
        duration = format_duration(info.get("duration"))
        views = compact_number(info.get("view_count"))

        quality_text = ", ".join(quality_values[1:]) or "Best available"

        self.title_label.configure(text=title)
        self.channel_label.configure(text=f"Channel: {uploader}")
        self.duration_label.configure(text=f"Duration: {duration}")
        self.views_label.configure(text=f"Views: {views}")
        self.resolution_label.configure(text=f"Available quality: {quality_text}")

        if thumbnail_bytes:
            try:
                image = Image.open(io.BytesIO(thumbnail_bytes)).convert("RGB")
                image.thumbnail((300, 169))
                self.thumbnail_image = ctk.CTkImage(
                    light_image=image,
                    dark_image=image,
                    size=image.size,
                )
                self.thumbnail_label.configure(image=self.thumbnail_image, text="")
            except Exception:
                pass

        self.status_var.set("Ready to download")
        self.detail_var.set("Video information loaded successfully.")

    def start_download(self):
        url = self.url_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not is_valid_youtube_url(url):
            messagebox.showerror("Invalid URL", "Please enter a valid YouTube URL.")
            return

        if not output_dir:
            messagebox.showerror("Missing folder", "Please choose a save folder.")
            return

        if self.mode_var.get() == "Audio (MP3)" and not shutil.which("ffmpeg"):
            messagebox.showerror(
                "FFmpeg required",
                "MP3 conversion requires FFmpeg. Install FFmpeg and restart the app.",
            )
            return

        os.makedirs(output_dir, exist_ok=True)

        self.cancel_requested = False
        self.progress_bar.set(0)
        self.percent_label.configure(text="0%")
        self.status_var.set("Preparing download...")
        self.detail_var.set("Connecting to YouTube.")
        self._set_busy(True, cancellable=True)

        mode = self.mode_var.get()
        quality = self.quality_var.get()
        ffmpeg_available = bool(shutil.which("ffmpeg"))

        threading.Thread(
            target=self._download_worker,
            args=(url, output_dir, mode, quality, ffmpeg_available),
            daemon=True,
        ).start()

    def cancel_download(self):
        self.cancel_requested = True
        self.status_var.set("Cancelling...")
        self.detail_var.set("Waiting for the current download operation to stop.")
        self.cancel_btn.configure(state="disabled")

    def _get_video_format(self, quality, ffmpeg_available):
        if quality == "Best":
            if ffmpeg_available:
                return "bv*+ba/b"
            return "best[ext=mp4]/best"

        height_map = {
            "2160p (4K)": 2160,
            "1440p": 1440,
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
        }
        height = height_map.get(quality, 1080)

        if ffmpeg_available:
            return (
                f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/"
                f"bv*[height<={height}]+ba/"
                f"b[height<={height}]/b"
            )

        return (
            f"b[height<={height}][ext=mp4]/"
            f"b[height<={height}]/"
            f"best[height<={height}]"
        )

    def _progress_hook(self, data):
        if self.cancel_requested:
            raise DownloadCancelled("Download cancelled by user.")

        status = data.get("status")

        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)

            percent = 0
            if total:
                percent = max(0, min(100, downloaded * 100 / total))

            speed = data.get("speed")
            eta = data.get("eta")

            details = []
            if speed:
                details.append(f"{speed / 1024 / 1024:.1f} MB/s")
            if eta is not None:
                details.append(f"ETA {eta}s")

            detail_text = "  •  ".join(details) if details else "Downloading media..."

            self.after(0, lambda p=percent: self.progress_bar.set(p / 100))
            self.after(0, lambda p=percent: self.percent_label.configure(text=f"{p:.0f}%"))
            self.after(0, lambda: self.status_var.set("Downloading..."))
            self.after(0, lambda t=detail_text: self.detail_var.set(t))

        elif status == "finished":
            self.after(0, lambda: self.progress_bar.set(1))
            self.after(0, lambda: self.percent_label.configure(text="100%"))
            self.after(0, lambda: self.status_var.set("Processing media..."))
            self.after(0, lambda: self.detail_var.set("Finalizing output with FFmpeg."))

    def _download_worker(
        self,
        url,
        output_dir,
        mode,
        quality,
        ffmpeg_available,
    ):
        try:
            common = {
                "outtmpl": os.path.join(
                    output_dir,
                    "%(title).180s [%(id)s].%(ext)s",
                ),
                "progress_hooks": [self._progress_hook],
                "noplaylist": True,
                "windowsfilenames": True,
                "quiet": True,
                "no_warnings": False,
            }

            if mode == "Audio (MP3)":
                bitrate = quality.split()[0]
                ydl_opts = {
                    **common,
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": bitrate,
                        }
                    ],
                }
            else:
                ydl_opts = {
                    **common,
                    "format": self._get_video_format(quality, ffmpeg_available),
                }
                if ffmpeg_available:
                    ydl_opts["merge_output_format"] = "mp4"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "Media")

            if self.cancel_requested:
                raise DownloadCancelled("Download cancelled by user.")

            self.after(0, lambda: self.progress_bar.set(1))
            self.after(0, lambda: self.percent_label.configure(text="100%"))
            self.after(0, lambda: self.status_var.set("Download complete"))
            self.after(0, lambda: self.detail_var.set(title))
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Download complete",
                    f"Saved successfully to:\n{output_dir}",
                ),
            )

        except DownloadCancelled:
            self.after(0, lambda: self.progress_bar.set(0))
            self.after(0, lambda: self.percent_label.configure(text="0%"))
            self.after(0, lambda: self.status_var.set("Download cancelled"))
            self.after(0, lambda: self.detail_var.set("No further data will be downloaded."))
        except Exception as exc:
            error_text = str(exc)

            if self.cancel_requested or "cancelled by user" in error_text.lower():
                self.after(0, lambda: self.status_var.set("Download cancelled"))
                self.after(0, lambda: self.detail_var.set("Download was cancelled."))
            else:
                self.after(0, lambda: self._show_error("Download failed", error_text))
        finally:
            self.after(0, lambda: self._set_busy(False))
            self.cancel_requested = False

    def _show_error(self, title, error_text):
        self.progress_bar.set(0)
        self.percent_label.configure(text="0%")
        self.status_var.set(title)
        self.detail_var.set("Check the error message and try again.")

        cleaned = error_text.replace("\x1b", "")
        messagebox.showerror(title, cleaned)


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "DilangaMalshan.YTDownloaderPro"
        )
    app = YouTubeDownloaderApp()
    app.mainloop()
