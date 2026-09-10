import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

import yt_dlp


APP_TITLE = "YT Downloader"
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads")


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


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("650x430")
        self.root.minsize(650, 430)

        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value=DEFAULT_DIR)
        self.type_var = tk.StringVar(value="MP4 Video")
        self.quality_var = tk.StringVar(value="1080p")
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="YouTube Downloader", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            main,
            text="Download videos you own or have permission to save.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 18))

        ttk.Label(main, text="YouTube URL").pack(anchor="w")
        url_entry = ttk.Entry(main, textvariable=self.url_var)
        url_entry.pack(fill="x", pady=(5, 14))
        url_entry.focus()

        options = ttk.Frame(main)
        options.pack(fill="x")

        left = ttk.Frame(options)
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(left, text="Download type").pack(anchor="w")
        type_box = ttk.Combobox(
            left,
            textvariable=self.type_var,
            values=["MP4 Video", "MP3 Audio"],
            state="readonly",
        )
        type_box.pack(fill="x", pady=(5, 14))
        type_box.bind("<<ComboboxSelected>>", self._on_type_change)

        right = ttk.Frame(options)
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(right, text="Video quality").pack(anchor="w")
        self.quality_box = ttk.Combobox(
            right,
            textvariable=self.quality_var,
            values=["Best", "2160p (4K)", "1440p", "1080p", "720p", "480p"],
            state="readonly",
        )
        self.quality_box.pack(fill="x", pady=(5, 14))

        ttk.Label(main, text="Save folder").pack(anchor="w")
        folder_row = ttk.Frame(main)
        folder_row.pack(fill="x", pady=(5, 14))

        ttk.Entry(folder_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_row, text="Browse", command=self.choose_folder).pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(main, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress.pack(fill="x", pady=(8, 6))

        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(0, 14))

        self.download_btn = ttk.Button(main, text="Download", command=self.start_download)
        self.download_btn.pack(fill="x", ipady=7)

        ttk.Label(
            main,
            text="Tip: 1080p/1440p/4K downloads usually need FFmpeg to merge video + audio.",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(14, 0))

    def _on_type_change(self, _event=None):
        if self.type_var.get() == "MP3 Audio":
            self.quality_box.configure(state="disabled")
        else:
            self.quality_box.configure(state="readonly")

    def choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.output_var.get() or DEFAULT_DIR)
        if selected:
            self.output_var.set(selected)

    def start_download(self):
        url = self.url_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not is_valid_youtube_url(url):
            messagebox.showerror("Invalid URL", "Please enter a valid YouTube URL.")
            return

        if not output_dir:
            messagebox.showerror("Missing folder", "Please choose a save folder.")
            return

        os.makedirs(output_dir, exist_ok=True)
        self.download_btn.configure(state="disabled")
        self.progress_var.set(0)
        self.status_var.set("Starting...")

        threading.Thread(
            target=self.download_media,
            args=(url, output_dir),
            daemon=True,
        ).start()

    def get_video_format(self):
        quality = self.quality_var.get()
        if quality == "Best":
            return "bv*+ba/b"

        height_map = {
            "2160p (4K)": 2160,
            "1440p": 1440,
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
        }
        h = height_map.get(quality, 1080)
        return (
            f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
            f"bv*[height<={h}]+ba/"
            f"b[height<={h}]/b"
        )

    def progress_hook(self, data):
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            if total:
                percent = max(0, min(100, downloaded * 100 / total))
                self.root.after(0, self.progress_var.set, percent)

            speed = data.get("speed")
            eta = data.get("eta")
            text = "Downloading..."
            if speed:
                text += f"  {speed / 1024 / 1024:.1f} MB/s"
            if eta is not None:
                text += f"  ETA {eta}s"
            self.root.after(0, self.status_var.set, text)
        elif status == "finished":
            self.root.after(0, self.progress_var.set, 100)
            self.root.after(0, self.status_var.set, "Processing media...")

    def download_media(self, url, output_dir):
        try:
            common = {
                "outtmpl": os.path.join(output_dir, "%(title).180s [%(id)s].%(ext)s"),
                "progress_hooks": [self.progress_hook],
                "noplaylist": True,
                "windowsfilenames": True,
                "quiet": True,
                "no_warnings": False,
            }

            if self.type_var.get() == "MP3 Audio":
                if not shutil.which("ffmpeg"):
                    raise RuntimeError("FFmpeg was not found. MP3 conversion requires FFmpeg.")

                ydl_opts = {
                    **common,
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
            else:
                ydl_opts = {
                    **common,
                    "format": self.get_video_format(),
                    "merge_output_format": "mp4",
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "Video")

            self.root.after(0, self.progress_var.set, 100)
            self.root.after(0, self.status_var.set, f"Completed: {title}")
            self.root.after(
                0,
                lambda: messagebox.showinfo("Done", f"Download completed.\n\nSaved to:\n{output_dir}"),
            )
        except Exception as exc:
            error_text = str(exc)
            self.root.after(0, self.progress_var.set, 0)
            self.root.after(0, self.status_var.set, "Download failed")
            self.root.after(0, lambda: messagebox.showerror("Download failed", error_text))
        finally:
            self.root.after(0, lambda: self.download_btn.configure(state="normal"))


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconname("YT Downloader")
    except Exception:
        pass
    YouTubeDownloaderApp(root)
    root.mainloop()
