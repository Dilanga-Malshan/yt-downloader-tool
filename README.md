# YT Downloader

A simple Windows Python GUI for downloading YouTube videos that you own or have permission to save.

## Features

- Paste a YouTube URL
- MP4 video or MP3 audio
- Best / 4K / 1440p / 1080p / 720p / 480p selection
- Choose output folder
- Progress bar
- Responsive GUI using a background download thread
- Uses `yt-dlp`
- FFmpeg support for merging high-quality streams and MP3 conversion

## Setup

### 1. Install Python

Install Python 3.11+ and make sure **Add Python to PATH** is enabled.

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install FFmpeg

FFmpeg is recommended for high-quality MP4 merging and required for MP3 conversion.

Verify the installation:

```powershell
ffmpeg -version
```

### 5. Run the app

```powershell
python youtube_downloader.py
```

## Build a Windows EXE

```powershell
pyinstaller --noconsole --onefile --name "YT-Downloader" youtube_downloader.py
```

The executable will be created at:

```text
dist\YT-Downloader.exe
```

> FFmpeg still needs to be available on the target computer's PATH unless you package it separately.

## Update yt-dlp

If YouTube changes and downloads stop working:

```powershell
pip install -U yt-dlp
```

## Usage note

Only download media you own, that is licensed for download, or that you otherwise have permission to save. Platform terms and copyright rules may restrict downloading some content.
