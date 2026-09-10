import io
import os
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import customtkinter as ctk
import yt_dlp
from PIL import Image


APP_TITLE = "YT Downloader Pro"
APP_SIZE = "1040x760"
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
        self.geometry(APP_SIZE)
        self.minsize(920, 680)

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
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            brand,
            text="YT Downloader Pro",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand,
            text="Modern desktop downloader powered by yt-dlp",
            text_color=("gray45", "gray70"),
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(3, 0))

        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.grid(row=0, column=1, sticky="e")

        self.ffmpeg_badge = ctk.CTkLabel(
            header_actions,
            text="Checking FFmpeg...",
            corner_radius=10,
            padx=12,
            pady=6,
        )
        self.ffmpeg_badge.pack(side="left", padx=(0, 10))

        self.theme_menu = ctk.CTkOptionMenu(
            header_actions,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            width=105,
            command=self._change_theme,
        )
        self.theme_menu.pack(side="left")

        body = ctk.CTkFrame(self, corner_radius=18)
        body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(22, 12), pady=22)
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(body, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 22), pady=22)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left,
            text="YouTube URL",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        url_row = ctk.CTkFrame(left, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew", pady=(8, 18))
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_row,
            textvariable=self.url_var,
            height=42,
            placeholder_text="https://www.youtube.com/watch?v=...",
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            url_row,
            text="Paste",
            width=76,
            height=42,
            command=self._paste_url,
        ).grid(row=0, column=1, padx=(8, 0))

        self.analyze_btn = ctk.CTkButton(
            url_row,
            text="Analyze",
            width=88,
            height=42,
            command=self.start_analyze,
        )
        self.analyze_btn.grid(row=0, column=2, padx=(8, 0))

        ctk.CTkLabel(
            left,
            text="Download mode",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=2, column=0, sticky="w")

        self.mode_selector = ctk.CTkSegmentedButton(
            left,
            values=["Video (MP4)", "Audio (MP3)"],
            variable=self.mode_var,
            command=self._on_mode_change,
            height=38,
        )
        self.mode_selector.grid(row=3, column=0, sticky="ew", pady=(8, 18))

        options = ctk.CTkFrame(left, fg_color="transparent")
        options.grid(row=4, column=0, sticky="ew")
        options.grid_columnconfigure((0, 1), weight=1)

        quality_box = ctk.CTkFrame(options, fg_color="transparent")
        quality_box.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        quality_box.grid_columnconfigure(0, weight=1)

        self.quality_label = ctk.CTkLabel(
            quality_box,
            text="Video quality",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.quality_label.grid(row=0, column=0, sticky="w")

        self.quality_menu = ctk.CTkOptionMenu(
            quality_box,
            values=self.video_quality_values,
            variable=self.quality_var,
            height=40,
        )
        self.quality_menu.grid(row=1, column=0, sticky="ew", pady=(7, 0))

        folder_box = ctk.CTkFrame(options, fg_color="transparent")
        folder_box.grid(row=0, column=1, sticky="ew", padx=(7, 0))
        folder_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            folder_box,
            text="Save folder",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        folder_row = ctk.CTkFrame(folder_box, fg_color="transparent")
        folder_row.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        folder_row.grid_columnconfigure(0, weight=1)

        self.folder_entry = ctk.CTkEntry(
            folder_row,
            textvariable=self.output_var,
            height=40,
        )
        self.folder_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            folder_row,
            text="Browse",
            width=72,
            height=40,
            command=self.choose_folder,
        ).grid(row=0, column=1, padx=(7, 0))

        progress_card = ctk.CTkFrame(left, corner_radius=12)
        progress_card.grid(row=5, column=0, sticky="ew", pady=(22, 14))
        progress_card.grid_columnconfigure(0, weight=1)

        status_row = ctk.CTkFrame(progress_card, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        status_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            status_row,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.percent_label = ctk.CTkLabel(status_row, text="0%")
        self.percent_label.grid(row=0, column=1, sticky="e")

        self.progress_bar = ctk.CTkProgressBar(progress_card, height=12)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            progress_card,
            textvariable=self.detail_var,
            text_color=("gray40", "gray70"),
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))

        action_row = ctk.CTkFrame(left, fg_color="transparent")
        action_row.grid(row=6, column=0, sticky="ew")
        action_row.grid_columnconfigure(0, weight=1)

        self.download_btn = ctk.CTkButton(
            action_row,
            text="Download",
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.start_download,
        )
        self.download_btn.grid(row=0, column=0, sticky="ew")

        self.cancel_btn = ctk.CTkButton(
            action_row,
            text="Cancel",
            width=90,
            height=46,
            fg_color=("gray75", "gray28"),
            hover_color=("gray65", "gray35"),
            state="disabled",
            command=self.cancel_download,
        )
        self.cancel_btn.grid(row=0, column=1, padx=(8, 0))

        self.open_folder_btn = ctk.CTkButton(
            action_row,
            text="Open Folder",
            width=105,
            height=46,
            fg_color=("gray75", "gray28"),
            hover_color=("gray65", "gray35"),
            command=self.open_output_folder,
        )
        self.open_folder_btn.grid(row=0, column=2, padx=(8, 0))

        ctk.CTkLabel(
            left,
            text="Download only media you own, that is licensed for download, or that you have permission to save.",
            wraplength=620,
            justify="left",
            text_color=("gray45", "gray65"),
            font=ctk.CTkFont(size=11),
        ).grid(row=7, column=0, sticky="w", pady=(16, 0))

        self.thumbnail_frame = ctk.CTkFrame(right, height=230, corner_radius=12)
        self.thumbnail_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 12))
        self.thumbnail_frame.grid_propagate(False)
        self.thumbnail_frame.grid_columnconfigure(0, weight=1)
        self.thumbnail_frame.grid_rowconfigure(0, weight=1)

        self.thumbnail_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="Video preview\nwill appear here",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("gray50", "gray60"),
        )
        self.thumbnail_label.grid(row=0, column=0, sticky="nsew")

        self.title_label = ctk.CTkLabel(
            right,
            text="No video analyzed",
            wraplength=330,
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        self.title_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 8))

        self.channel_label = ctk.CTkLabel(
            right,
            text="Channel: —",
            anchor="w",
            text_color=("gray40", "gray70"),
        )
        self.channel_label.grid(row=2, column=0, sticky="ew", padx=16, pady=3)

        self.duration_label = ctk.CTkLabel(
            right,
            text="Duration: —",
            anchor="w",
            text_color=("gray40", "gray70"),
        )
        self.duration_label.grid(row=3, column=0, sticky="ew", padx=16, pady=3)

        self.views_label = ctk.CTkLabel(
            right,
            text="Views: —",
            anchor="w",
            text_color=("gray40", "gray70"),
        )
        self.views_label.grid(row=4, column=0, sticky="ew", padx=16, pady=3)

        self.resolution_label = ctk.CTkLabel(
            right,
            text="Available quality: —",
            anchor="w",
            wraplength=330,
            justify="left",
            text_color=("gray40", "gray70"),
        )
        self.resolution_label.grid(row=5, column=0, sticky="ew", padx=16, pady=(3, 16))

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
                image.thumbnail((360, 210))
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
    app = YouTubeDownloaderApp()
    app.mainloop()
