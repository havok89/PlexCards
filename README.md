# PlexCards 🎬🎨

[![Version](https://img.shields.io/github/v/release/havok89/PlexCards?include_prereleases&label=version&color=orange)](https://github.com/havok89/PlexCards/releases)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=FFD62E)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org/)

**PlexCards** is an automated title card and artwork studio for your Plex TV libraries. It bridges the gap between community-crafted [MediUX](https://mediux.pro/) sets and immediate, automated local title card generation with real-time preview and optional Google Gemini AI styling.

Whether you want consistent artwork for airing series before designers upload to MediUX, custom gradient cards inspired by *Star Trek: Strange New Worlds*, or one-click automated artwork sync the moment an episode downloads, PlexCards handles it effortlessly.

---

## ✨ Features

### 1. 🖼️ MediUX Auto-Matching & Coverage Analysis
- **Automatic Set Discovery:** Scans your TV library and matches available sets directly from [MediUX](https://mediux.pro/).
- **Season Coverage Intelligence:** Calculates the exact season coverage of every set against what you actually have downloaded in Plex (e.g., *“3 of 4 seasons covered”*), preventing incomplete or abandoned sets.
- **Preferred Artists:** Set preferred MediUX creator names (e.g., `rhodesydesign`, `polymath-art`) to automatically select your favorite designers across your library.
- **One-Click Batch Apply:** Apply title cards for entire seasons or all available episodes in seconds directly through the Plex API.

### 2. 🎨 Studio Title Card Generator Engine
- **Crisp 1080p Title Cards:** Renders ultra-clean episode cards on high-resolution TMDb backdrops and stills.
- **Side-Stack Gradient Preset:** Modern horizontal or vertical dark gradient overlay (left, right, top, bottom) ensuring 100% typography legibility across any bright or busy backdrop.
- **Full Typography Control:**
  - Bundled premium Google fonts (*Oswald, Inter, Cinzel, Bebas Neue, Playfair Display, Anton, Barlow Condensed, Rubik, and more*).
  - Custom `.ttf` and `.otf` font uploader built right into the UI.
  - Granular font sizing slider (50pt – 180pt) and customizable title/subtitle distance offset.
  - Subheading formatting: season/episode markers, uppercase toggles, and individual color pickers.
- **Interactive Live Preview Canvas:** Switch between episodes in real-time to preview typography, color palettes, and gradients against live backdrops before saving.

### 3. 🤖 Optional Gemini AI Style Assistant
- **Show-Aware Typography & Color Styling:** Powered by Google Gemini (`gemini-3.5-flash-lite`), the assistant analyzes your show’s title, genres, and synopsis to recommend matching fonts, colors, and layouts.
- **Natural Language Prompts:** Give creative prompts like *"dark 1980s neon synthwave thriller with bold yellow font"* to let Gemini restyle cards on the fly.
- **100% Optional & Zero-Clutter:** If `GEMINI_API_KEY` is not provided in your `.env`, all AI elements, buttons, and loaders are automatically hidden. Everything works completely offline/locally without an API key!

### 4. ⚡ Real-Time Plex WebSocket Listener
- **Instant Event Sync:** Listens to Plex Media Server’s live WebSocket event stream (`/ws/notifications`).
- **Instant Card Application:** When a new episode finishes scanning into your library, PlexCards immediately generates and uploads the title card without waiting for a scheduled poll.

### 5. 🌐 Cloudflare & Remote Access Ready
- **Lightweight Poster Thumbnails:** High-resolution posters are automatically compressed and resized using PIL from ~2.5MB down to ~45KB–60KB (**96%+ bandwidth savings**), keeping grid views lightning fast even on cellular data.
- **Edge Caching & ETag Support:** Served with `Cache-Control` and `ETag` (HTTP 304 Not Modified), utilizing zero tunnel bandwidth on repeat visits.

### 6. 🔍 Dual Provider Engine (TheTVDB & TMDb)
- **TheTVDB (v4) Prioritization:** First-class support for libraries managed with Sonarr and Plex's TheTVDB ordering.
- **Subscriber PIN Support:** Full compatibility with TheTVDB v4 subscriber accounts and personal API keys.
- **Provider Cascade:** Prioritize TheTVDB for community episode screencaps, accurate season numbering, and broadcast statuses (`Continuing` vs `Ended`), with automatic fallback to TMDb.
- **MediUX Bridge:** Automatically resolves and translates TVDB IDs to TMDb IDs so community MediUX sets match effortlessly even when Plex only indexes TVDB GUIDs.
- **Smart Candidate Stills:** Browse and select candidate stills from both TheTVDB and TMDb with clear provider badges.

### 7. 🔍 TMDb Search & Plex Fix-Match Studio
- **Smart Title Normalization:** Cleans roman numerals, release years, and country codes to maximize match accuracy.
- **Built-In Search:** Search and link alternative IDs directly inside the app if Plex mismatched a series.
- **Push Fix-Match to Plex:** Push corrected GUIDs back to your Plex Media Server directly from the studio.
- **Continuing vs. Ended Filter:** Filter your library by active airing shows (`Continuing` / `Returning Series`) versus concluded shows (`Ended`).

### 8. 🔒 Plex OAuth Authentication
- **Secure by Default:** Protect your dashboard with official Plex OAuth sign-in (`ENABLE_AUTH=true`).
- **Owner & Multi-User Whitelist:** Restricts access to the Plex Media Server owner by default, with an optional username/email whitelist (`ALLOWED_USERS`).
- **Signed Session Cookies:** Secure HMAC-SHA256 browser session handling.

### 9. 🛡️ Safe Testing Mode
- **Dry-Run Protection:** `TEST_MODE=true` is enabled by default. You can experiment with fonts, test layouts, and generate previews without writing any changes to your real Plex library until you're ready.

---

## 🚀 Quick Start with Docker (Recommended)

The easiest way to run PlexCards is using Docker and Docker Compose. A multi-stage `Dockerfile` packages the React frontend and FastAPI backend into a single container.

### 1. Clone the Repository
```bash
git clone https://github.com/havok89/PlexCards.git
cd PlexCards
```

### 2. Configure Environment Variables
Copy the template file:
```bash
cp .env.example .env
```
Open `.env` in your favorite editor and fill in your details (see the [Environment Variables Guide](#-environment-variables-guide) below):
```bash
nano .env
```

### 3. Launch the Container
```bash
docker compose up -d --build
```

### 4. Open the Web Dashboard
Navigate to:
```
http://localhost:8080
```
*(or `http://<your-server-ip>:8080`)*

---

## ⚙️ Environment Variables Guide

Here is the complete list of variables supported in `.env`:

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `PLEX_URL` | **Yes** | `http://localhost:32400` | Address of your Plex Media Server (e.g. `http://192.168.1.50:32400`). |
| `PLEX_TOKEN` | **Yes** | — | Your Plex authentication token (X-Plex-Token). |
| `PLEX_TV_LIBRARY` | **Yes** | `TV Shows` | The exact name of your TV library section in Plex. |
| `TMDB_API_KEY` | **Yes** | — | Free TMDb v3 API key or v4 read token for fetching episode stills and metadata. |
| `TVDB_API_KEY` | *No* | — | TheTVDB v4 Project API Key for episode stills and series metadata. |
| `TVDB_PIN` | *No* | — | TheTVDB Subscriber PIN (required if your TVDB account has a subscriber subscription). |
| `DEFAULT_METADATA_PROVIDER` | *No* | `tvdb` | Primary metadata provider for stills and series status (`tvdb` or `tmdb`). |
| `GEMINI_API_KEY` | *No* | — | Google Gemini API key for AI style suggestions. *(If omitted, AI UI features are hidden).* |
| `GEMINI_MODEL` | *No* | `gemini-3.5-flash-lite` | Gemini model to use. `gemini-3.5-flash-lite` offers a generous free tier (up to 500 requests/day). |
| `MEDIUX_API_TOKEN` | *No* | — | Optional MediUX API token if you have beta/private account access. |
| `FANART_API_KEY` | *No* | — | Optional Fanart.tv API key for additional fallback show logos. |
| `TEST_MODE` | *No* | `true` | When `true`, prevents any modifications or uploads to your Plex server while testing. Set to `false` when ready for live sync. |
| `ENABLE_AUTH` | *No* | `false` | Set to `true` to require users to sign in via Plex OAuth. |
| `ALLOWED_USERS` | *No* | — | Comma-separated list of Plex usernames or emails allowed to sign in (defaults to Plex server owner only). |
| `SECRET_KEY` | *No* | — | Secret key for signing session cookies (auto-generated in SQLite if left empty). |
| `PORT` | *No* | `8080` | Port the web dashboard and API server listens on. |
| `HOST` | *No* | `0.0.0.0` | Bind IP for the backend server. |
| `POLL_INTERVAL_HOURS`| *No* | `12` | Background poll interval in hours to check for new episodes and MediUX updates. |

---

## 🔑 How to Get Your API Keys

### 1. Plex Authentication Token (`PLEX_TOKEN`)
1. Open Plex Web in your browser and play any media.
2. Click the three dots (**...**) on any media item > **Get Info** > **View XML**.
3. Look at the URL bar at the very end for `X-Plex-Token=...`.
4. Copy this string into `PLEX_TOKEN`.
> Refer to the official [Plex Support Guide on Finding Tokens](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) for full details.

### 2. The Movie Database Key (`TMDB_API_KEY`)
1. Create a free account at [TheMovieDB.org](https://www.themoviedb.org/).
2. Go to **Settings** > [API](https://www.themoviedb.org/settings/api).
3. Request an API key (choose "Developer").
4. Copy the **API Key (v3 auth)** into `TMDB_API_KEY`.

### 3. TheTVDB v4 Key & Subscriber PIN (`TVDB_API_KEY` & `TVDB_PIN`) *(Optional)*
1. Log in to [TheTVDB.com](https://thetvdb.com/).
2. Go to your **Account Dashboard** > [API Keys](https://thetvdb.com/dashboard/account/apikeys) and generate a **v4 Project API Key**.
3. If you have an active TVDB subscription, locate your **Subscriber PIN** under your subscription / account settings.
4. Copy the key to `TVDB_API_KEY` and the PIN to `TVDB_PIN`.
> *(When configured, PlexCards can prioritize TVDB for screencaps and status data while maintaining MediUX matching).*

### 4. Google Gemini Key (`GEMINI_API_KEY`) *(Optional)*
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Get API key** and create a free key in a Google Cloud project.
3. Paste the key into `GEMINI_API_KEY`.
*(Note: If left blank, PlexCards runs with all manual styling features enabled and AI components cleanly hidden).*

---

## 🛠️ Manual Installation (Without Docker)

If you prefer to run PlexCards natively on your host machine:

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & **npm**

### 1. Clone & Set Up Backend
```bash
git clone https://github.com/havok89/PlexCards.git
cd PlexCards

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
nano .env  # Add your Plex and TMDb credentials
```

### 3. Build the Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Start the Application
```bash
python main.py
```
Open your browser at `http://localhost:8080`.

---

## 💻 Frontend Development (HMR)

If you are developing or modifying the React UI:
1. Start the backend:
   ```bash
   python main.py
   ```
2. In a separate terminal, start the Vite dev server with Hot Module Reloading:
   ```bash
   cd frontend
   npm run dev
   ```
3. Open `http://localhost:5173`. API requests will automatically proxy to the backend on `http://localhost:8080`.

---

## 📂 Persistent Data & Storage

When using Docker, the following folders are mapped as persistent volumes:
- `./data`: SQLite database (`plexcards.db` / `plexposters.db`), storing show states, style configurations, and user preferences.
- `./cache`: Downloaded Google fonts, cached episode stills, thumbnail posters, and temporary preview renders.
- `./custom_fonts`: Any custom `.ttf` or `.otf` fonts uploaded through the web UI studio.

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome!
1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
