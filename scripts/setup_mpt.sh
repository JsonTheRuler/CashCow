#!/usr/bin/env bash
# Cash Cow — MoneyPrinterTurbo setup script
# Clones, installs, configures, and patches MPT for the Cash Cow pipeline.
#
# Usage: bash scripts/setup_mpt.sh [PEXELS_API_KEY]
#
# Prerequisites: Python 3.12, ffmpeg, git

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MPT_DIR="$PROJECT_DIR/MoneyPrinterTurbo"

echo "=== Cash Cow — MoneyPrinterTurbo Setup ==="

# 1. Clone if needed
if [ ! -d "$MPT_DIR" ]; then
    echo "[1/5] Cloning MoneyPrinterTurbo..."
    git clone https://github.com/harry0703/MoneyPrinterTurbo.git "$MPT_DIR"
else
    echo "[1/5] MoneyPrinterTurbo already cloned."
fi

# 2. Create venv and install deps
echo "[2/5] Setting up Python venv..."
if [ ! -d "$MPT_DIR/.venv" ]; then
    python3 -m venv "$MPT_DIR/.venv"
fi
source "$MPT_DIR/.venv/bin/activate" 2>/dev/null || source "$MPT_DIR/.venv/Scripts/activate"
pip install -r "$MPT_DIR/requirements.txt" -q
pip install "edge_tts>=7.2.0" -q

# 3. Copy config
echo "[3/5] Configuring..."
cp "$PROJECT_DIR/config/turbo_config.toml" "$MPT_DIR/config.toml"
if [ -n "${1:-}" ]; then
    # Inject Pexels API key if provided
    sed -i "s/pexels_api_keys = \[\]/pexels_api_keys = [\"$1\"]/" "$MPT_DIR/config.toml"
    echo "  Pexels API key configured."
else
    echo "  WARNING: No Pexels API key. Pass it as first argument or edit config.toml."
fi

# 4. Apply edge_tts v7 patches
echo "[4/5] Applying edge_tts v7 compatibility patches..."
python "$SCRIPT_DIR/patch_mpt_voice.py" "$MPT_DIR/app/services/voice.py"

# 5. Apply video transition fix
echo "[5/5] Applying video transition fix..."
python "$SCRIPT_DIR/patch_mpt_video.py" "$MPT_DIR/app/services/video.py"

echo ""
echo "=== Setup complete ==="
echo "Start MPT:  cd $MPT_DIR && source .venv/bin/activate && python main.py"
echo "API docs:   http://127.0.0.1:8080/docs"
echo "Streamlit:  streamlit run $MPT_DIR/webui/Main.py --server.port 8501"
