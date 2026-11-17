# BypassNow.gg

Ad-free, low-latency cloud gaming bypass platform for now.gg.

## Features
- Complete catalog of 120+ games across 26 categories directly embedded
- Real-time instant game search
- Automated now.gg guest session authentication & token caching
- Ad bypass, stream optimizer & borderless fullscreen stage
- Zero dependencies (runs on pure Python standard library)

## Running Locally
```bash
python server.py
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

## Cloud Deployment (Render / Railway / Koyeb)
- **Start Command**: `python server.py`
- Automatically respects `$PORT` and `$HOST` (`0.0.0.0`).
