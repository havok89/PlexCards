# PlexPosters 🎬🎨

**PlexPosters** is an automated title card and artwork manager for Plex TV libraries. It bridges the gap between community-crafted MediUX artwork and immediate, local title card generation.

---

## 🌟 Key Features

1. **Live MediUX Auto-Matching (with Season Coverage Checking):**
   * Scans your TV shows and finds sets on [MediUX](https://mediux.pro/).
   * Checks your library's seasons to ensure the set actually covers what you have in Plex, preventing incomplete or abandoned sets.
   * Periodically polls MediUX for newly uploaded episode cards on currently airing shows.

2. **Customizable Lightweight Card Generator:**
   * Generates crisp 1080p title cards locally using official TMDb episode stills and typography.
   * **Side-Stack Gradient Preset (Like *Star Trek: Strange New Worlds*):** Smooth horizontal gradient on the left, bold condensed typography, tracked sub-header (`SEASON FOUR ▲ EPISODE FIVE`), and vector divider icons (Starfleet Delta, dots, dashes).
   * Ensures 100% legibility over any bright or busy backdrop.

3. **Per-Show Control Modes:**
   * **`Auto (MediUX with Fallback)` (Default):** Applies MediUX cards when available, auto-generates interim cards for missing/newly aired episodes, and silently upgrades them once the designer uploads to MediUX.
   * **`Generator Only (Preset)`:** Never checks MediUX. Permanently renders cards using your assigned preset and style.
   * **`Ignored`:** Leaves the show untouched.

4. **Modern Web UI Dashboard:**
   * Interactive live-preview canvas: adjust fonts, colors, and gradients and see real-time updates on actual episode stills from your library.
   * **✨ AI Style Assistant (Powered by Gemini):** Give natural language prompts (e.g. *"dark moody crime thriller with white serif font"*) to auto-tune fonts, palettes, and layouts.
   * Direct "Apply to Plex" button to update episode artwork via Plex API with a single click.

---

## 🚀 Quick Start

### 1. Configure Environment
Copy the template and fill in your details:
```bash
cp .env.example .env
```
Key settings:
* `PLEX_URL`: Your Plex server address (e.g., `http://localhost:32400` or `http://192.168.x.x:32400`)
* `PLEX_TOKEN`: Your Plex authentication token (X-Plex-Token)
* `PLEX_TV_LIBRARY`: Name of your TV library section (e.g., `TV shows`)
* `TMDB_API_KEY`: Free Developer API key from [themoviedb.org](https://www.themoviedb.org/)
* `GEMINI_API_KEY`: *(Optional)* For AI typography and styling recommendations
* `TEST_MODE`: `true` (Default, keeps Plex safe while testing by preventing server uploads)

### 2. Running with Docker (Recommended) 🐳

PlexPosters includes a multi-stage Dockerfile that bundles the React frontend and FastAPI backend into a single container.

1. **Start with Docker Compose:**
   ```bash
   docker compose up -d --build
   ```

2. **Access the Dashboard:**
   Open your browser at `http://localhost:8080` (or `http://<your-host-ip>:8080`).

#### Persistent Volumes:
* `./data:/app/data`: Stores the SQLite database (`plexposters.db`), show settings, and custom presets.
* `./cache:/app/cache`: Stores downloaded Google fonts, episode stills, and test outputs.
* `./custom_fonts:/app/custom_fonts`: Stores custom `.ttf` and `.otf` fonts uploaded through the web UI.

---

### 3. Running Locally (Python + React)
```bash
# Activate virtual environment
source .venv/bin/activate

# Start server
python main.py
```
Open your browser to:
```
http://localhost:8080
```

### 3. Frontend Development (Optional)
If you want to modify the React frontend with Vite Hot Module Reloading:
```bash
cd frontend
npm run dev
```
Visit `http://localhost:5173` (API requests are automatically proxied to the FastAPI backend).
To rebuild the production bundle served by `python main.py`:
```bash
npm run build
```
