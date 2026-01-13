#!/bin/bash
# RunPod Setup Script for InfiniteTalk with LoRA (for long videos)
# Optimized for: H100 80GB or A100 80GB
# For minute-long videos with fast generation
# Mount your network volume at /workspace/weights before running

set -e

WEIGHTS_DIR="/workspace/weights"
REPO_DIR="/workspace/InfiniteTalk"

echo "=========================================="
echo "InfiniteTalk RunPod Setup (LoRA Optimized)"
echo "=========================================="

# Check if weights directory exists (network volume mounted)
if [ ! -d "$WEIGHTS_DIR" ]; then
    echo "ERROR: Network volume not mounted at $WEIGHTS_DIR"
    echo "Please attach your network volume with mount path: /workspace/weights"
    exit 1
fi

# Install system dependencies
echo ""
echo "[1/7] Installing system dependencies..."
apt-get update && apt-get install -y ffmpeg libsndfile1 espeak-ng git-lfs

# Clone or update repo
echo ""
echo "[2/7] Setting up InfiniteTalk repository..."
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
    git pull
else
    cd /workspace
    git clone https://github.com/MeiGen-AI/InfiniteTalk.git
    cd "$REPO_DIR"
fi

# Symlink weights
ln -sfn "$WEIGHTS_DIR" "$REPO_DIR/weights"

# Create venv
echo ""
echo "[3/7] Setting up Python virtual environment..."
python3 -m venv /opt/venv
source /opt/venv/bin/activate

# Install Python dependencies
echo ""
echo "[4/7] Installing Python dependencies..."

# Core PyTorch (CUDA 12.4 for H100/A100)
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

# xformers for memory efficiency
pip install xformers --index-url https://download.pytorch.org/whl/cu124

# Build dependencies for flash-attn
pip install packaging wheel ninja

# Flash attention (skip if fails - not critical with LoRA)
pip install flash-attn --no-build-isolation || echo "Warning: flash-attn install failed, continuing..."

# Core dependencies
pip install -r requirements.txt
pip install gradio easydict soundfile librosa decord scenedetect pyloudnorm moviepy imageio-ffmpeg num2words spacy phonemizer espeakng-loader
pip install misaki==0.7.0 kokoro

# Download spacy model
python -m spacy download en_core_web_sm

# Patch compatibility issues
sed -i 's/from inspect import ArgSpec/# from inspect import ArgSpec/' wan/multitalk.py
sed -i "s/Wav2Vec2Model.from_pretrained(wav2vec, local_files_only=True)/Wav2Vec2Model.from_pretrained(wav2vec, local_files_only=True, attn_implementation='eager')/" app.py
sed -i 's/server_port=8418/server_port=7860/' app.py

# Set HuggingFace cache
export HF_HOME=/workspace/weights/.hf_cache

# Download models if not present
echo ""
echo "[5/7] Checking/downloading base models..."

# Wan2.1 base model (~70GB)
if [ ! -f "$WEIGHTS_DIR/Wan2.1-I2V-14B-480P/diffusion_pytorch_model-00007-of-00007.safetensors" ]; then
    echo "Downloading Wan2.1-I2V-14B-480P (~70GB)... This will take a while."
    huggingface-cli download Wan-AI/Wan2.1-I2V-14B-480P --local-dir "$WEIGHTS_DIR/Wan2.1-I2V-14B-480P"
else
    echo "✓ Wan2.1-I2V-14B-480P already downloaded"
fi

# Chinese wav2vec2 audio encoder (~1.5GB)
if [ ! -f "$WEIGHTS_DIR/chinese-wav2vec2-base/model.safetensors" ]; then
    echo "Downloading chinese-wav2vec2-base..."
    huggingface-cli download TencentGameMate/chinese-wav2vec2-base --local-dir "$WEIGHTS_DIR/chinese-wav2vec2-base"
    # Also get safetensors version
    huggingface-cli download TencentGameMate/chinese-wav2vec2-base model.safetensors --revision refs/pr/1 --local-dir "$WEIGHTS_DIR/chinese-wav2vec2-base" || echo "Note: safetensors version download failed, using pytorch_model.bin"
else
    echo "✓ chinese-wav2vec2-base already downloaded"
fi

# InfiniteTalk base weights (~19GB)
if [ ! -f "$WEIGHTS_DIR/InfiniteTalk/single/infinitetalk.safetensors" ]; then
    echo "Downloading InfiniteTalk base weights (~19GB)..."
    huggingface-cli download MeiGen-AI/InfiniteTalk single/infinitetalk.safetensors multi/infinitetalk.safetensors --local-dir "$WEIGHTS_DIR/InfiniteTalk"
else
    echo "✓ InfiniteTalk base weights already downloaded"
fi

# Download LoRA models for speed (CRITICAL FOR LONG VIDEOS)
echo ""
echo "[6/7] Downloading LoRA models for fast generation..."

if [ ! -d "$WEIGHTS_DIR/InfiniteTalk-LoRA-FusionX" ]; then
    echo "Downloading InfiniteTalk-LoRA-FusionX..."
    huggingface-cli download MeiGen-AI/InfiniteTalk-LoRA-FusionX --local-dir "$WEIGHTS_DIR/InfiniteTalk-LoRA-FusionX"
    echo "✓ LoRA models downloaded"
else
    echo "✓ LoRA models already present"
fi

# Verify all files
echo ""
echo "[7/7] Verifying installation..."
MISSING=0

check_file() {
    if [ ! -f "$1" ]; then
        echo "✗ Missing: $1"
        MISSING=1
    fi
}

check_file "$WEIGHTS_DIR/Wan2.1-I2V-14B-480P/diffusion_pytorch_model-00001-of-00007.safetensors"
check_file "$WEIGHTS_DIR/Wan2.1-I2V-14B-480P/Wan2.1_VAE.pth"
check_file "$WEIGHTS_DIR/Wan2.1-I2V-14B-480P/models_t5_umt5-xxl-enc-bf16.pth"

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "WARNING: Some files are missing. Re-run this script or download manually."
else
    echo "✓ All critical model files present"
fi

# Done
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "OPTIMIZED FOR LONG VIDEOS (up to 60+ seconds)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RECOMMENDED: LoRA Mode (5-6x faster, less VRAM)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Gradio UI with LoRA:"
echo "  cd $REPO_DIR && source /opt/venv/bin/activate"
echo "  python app.py \\"
echo "    --ckpt_dir weights/Wan2.1-I2V-14B-480P \\"
echo "    --wav2vec_dir weights/chinese-wav2vec2-base \\"
echo "    --infinitetalk_dir weights/InfiniteTalk/single/infinitetalk.safetensors \\"
echo "    --lora_dir weights/InfiniteTalk-LoRA-FusionX \\"
echo "    --num_persistent_param_in_dit 0 \\"
echo "    --sample_steps 8 \\"
echo "    --use_teacache \\"
echo "    --use_apg"
echo ""
echo "CLI generation with LoRA:"
echo "  cd $REPO_DIR && source /opt/venv/bin/activate"
echo "  python generate_infinitetalk.py \\"
echo "    --ckpt_dir weights/Wan2.1-I2V-14B-480P \\"
echo "    --wav2vec_dir weights/chinese-wav2vec2-base \\"
echo "    --infinitetalk_dir weights/InfiniteTalk/single/infinitetalk.safetensors \\"
echo "    --lora_dir weights/InfiniteTalk-LoRA-FusionX \\"
echo "    --input_json your_input.json \\"
echo "    --sample_steps 8 \\"
echo "    --size infinitetalk-480"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "FALLBACK: Standard Mode (slower, more VRAM)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Only use if LoRA quality isn't satisfactory:"
echo "  python app.py \\"
echo "    --ckpt_dir weights/Wan2.1-I2V-14B-480P \\"
echo "    --wav2vec_dir weights/chinese-wav2vec2-base \\"
echo "    --infinitetalk_dir weights/InfiniteTalk/single/infinitetalk.safetensors \\"
echo "    --num_persistent_param_in_dit 0 \\"
echo "    --sample_steps 25"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "GPU Recommendations:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  • H100 80GB: Best for long videos with LoRA"
echo "  • A100 80GB: Works with LoRA + optimizations"
echo "  • If still OOM: Reduce --sample_steps to 4-6"
echo "               or use --size infinitetalk-480"
echo ""
echo "Performance: ~8-10min for 60s video with LoRA vs 1h+ without"
echo ""
