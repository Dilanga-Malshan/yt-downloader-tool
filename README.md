# YT Downloader Pro

A modern Windows desktop GUI for downloading YouTube videos that you own or have permission to save.

## Highlights

- Modern CustomTkinter interface
- Dark / Light / System theme selector
- Paste + Analyze workflow
- Video thumbnail preview
- Video title, channel, duration and view count
- Dynamic quality detection
- MP4 video downloads
- MP3 audio extraction with selectable bitrate
- 4K / 1440p / 1080p / 720p / 480p / 360p support when available
- Progress percentage, speed and ETA
- Cancel download button
- Open output folder button
- FFmpeg status badge
- Graceful video fallback when FFmpeg is unavailable
- Background threads so the UI stays responsive

## Requirements

- Python 3.11+
- FFmpeg recommended for high-quality video merging
- FFmpeg required for MP3 conversion

## Setup

Open PowerShell in the project folder.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Install FFmpeg on Windows

```powershell
winget install --id Gyan.FFmpeg -e
```

Close and reopen PowerShell/PyCharm after installation, then verify:

```powershell
ffmpeg -version
```

## Run

```powershell
python youtube_downloader.py
```

## If you already cloned an older version

Pull the latest code and update dependencies:

```powershell
git pull origin main
python -m pip install -r requirements.txt
python youtube_downloader.py
```

## Build a Windows EXE

```powershell
pyinstaller --noconsole --onefile --name "YT-Downloader-Pro" youtube_downloader.py
```

The executable will be created in:

```text
dist\YT-Downloader-Pro.exe
```

FFmpeg still needs to be available on the target computer's PATH for MP3 conversion and high-quality video/audio merging unless you bundle it separately.

## Update yt-dlp

YouTube changes regularly. If extraction stops working, update yt-dlp:

```powershell
python -m pip install -U yt-dlp
```

## Usage note

Only download media you own, that is licensed for download, or that you otherwise have permission to save. Platform terms and copyright rules may restrict downloading some content.
