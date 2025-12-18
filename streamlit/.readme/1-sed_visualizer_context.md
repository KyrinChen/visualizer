# Streamlit Visualizer Development Context

## 1. Project Overview
Developed a modular, extensible Streamlit-based visualization tool for SED (Sound Event Detection) models. The goal was to decouple the visualization logic from specific models/datasets, allowing for easy expansion.

## 2. Directory Structure
Path: `/inspire/ssd/project/embodied-multimodality/public/jqchen/tools/visualizer/streamlit/`

- **`src/`**: Shared utility library.
  - `utils.py`: Common functions for recursive JSONL loading, path resolution (`resolve_path`), and MIME type guessing.
- **`app_pretrained_sed.py`**: Visualization script specifically for the PretrainedSED model.
  - Features: Multi-threshold Tabs (0.1/0.2/0.5), Timeline Gantt Chart (Altair), Audio Player.
  - Navigation: Sidebar file selector (Folder/File level), Item selector dropdown + Prev/Next buttons (Session State synced).
- **`app_dasm.py`**: Legacy visualization script for DASM model (refactored to use `src/utils`).
- **`run_pretrained_sed.sh`**: Startup script.
  - Automatically handles `PYTHONPATH`.
  - Disables file watcher (`--server.fileWatcherType none`) to avoid `inotify` limit errors.

## 3. Key Technical Decisions
- **Recursive File Scanning**: `src/utils.py` uses `rglob` to scan all subdirectories, using relative paths as keys to support nested dataset structures.
- **UI Interaction**:
  - **Dual-level File Selection**: "Filter by Folder" -> "Select File" to handle large numbers of files cleanly.
  - **Robust Navigation**: Combined `st.selectbox` and `st.button` using `on_click`/`on_change` callbacks and `st.session_state` to ensure bidirectional synchronization between the dropdown and prev/next buttons.
- **Independence**: Each model (SED, DASM) has its own independent `app_xxx.py` entry point to avoid a monolithic `app.py`, while sharing core logic via `src/`.

## 4. Usage
cd /inspire/ssd/project/embodied-multimodality/public/jqchen/tools/visualizer/streamlit/
bash run_pretrained_sed.sh## 5. Dependencies
- `streamlit`
- `pandas`
- `altair`