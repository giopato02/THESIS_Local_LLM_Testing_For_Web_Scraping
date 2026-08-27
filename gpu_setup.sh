#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-command setup and launch for the CKL GPU node.
#
# Safe to run repeatedly. Every step checks whether it is already done, so
# after a dropped session you re-run the same command and it picks up where it
# stopped -- including the benchmark itself, which skips completed runs.
#
#   bash gpu_setup.sh          set up, verify the GPU, start the grid
#   bash gpu_setup.sh --check   report status only, change nothing
# ---------------------------------------------------------------------------
set -uo pipefail

DIR="$HOME/Web_Scraping_Engine"
MODELS="llama3.1:8b qwen2.5-coder:7b gemma4:12b"
LOG="$DIR/results/stage_a_gpu.log"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
ok()  { printf '    \033[32mok\033[0m  %s\n' "$1"; }
bad() { printf '    \033[31m!!\033[0m  %s\n' "$1"; }

# --- status only -----------------------------------------------------------
if [ "${1:-}" = "--check" ]; then
  say "status"
  pgrep -f "benchmark.py" >/dev/null && ok "benchmark RUNNING" || bad "benchmark not running"
  if [ -f "$DIR/results/benchmark_results.csv" ]; then
    n=$(( $(wc -l < "$DIR/results/benchmark_results.csv") - 1 ))
    ok "$n / 540 runs complete"
  fi
  [ -f "$LOG" ] && tail -3 "$LOG"
  exit 0
fi

# --- 1. unpack -------------------------------------------------------------
say "unpacking"
if [ ! -d "$DIR" ]; then
  [ -f "$HOME/neohub.tar.gz" ] || { bad "neohub.tar.gz not found in $HOME -- upload it first"; exit 1; }
  tar xzf "$HOME/neohub.tar.gz" -C "$HOME" && ok "extracted"
else
  ok "already extracted"
fi
cd "$DIR" || exit 1

# --- 2. ollama -------------------------------------------------------------
say "ollama"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
pgrep -x ollama >/dev/null || { nohup ollama serve > /tmp/ollama.log 2>&1 & sleep 8; }
pgrep -x ollama >/dev/null && ok "server up" || { bad "server failed -- see /tmp/ollama.log"; exit 1; }

# Pull anything missing. ~17 GB total; already-present models are instant.
for m in $MODELS; do
  if ollama list 2>/dev/null | grep -q "^${m%%:*}"; then ok "$m present"
  else say "pulling $m"; ollama pull "$m" || bad "pull failed: $m"; fi
done

# --- 3. python environment -------------------------------------------------
say "python environment"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && ok "venv created"
else ok "venv present"; fi
.venv/bin/python -c "import ollama, bs4, requests" 2>/dev/null || {
  .venv/bin/pip install -q requests beautifulsoup4 lxml ollama pandas \
      matplotlib openpyxl python-docx ddgs && ok "packages installed"; }
.venv/bin/python -c "import ollama, bs4, requests; print('    ok  imports fine')"

# --- 4. GPU check ----------------------------------------------------------
# The critical gate. Ollama silently falls back to CPU when it cannot see
# CUDA, which would look like a working run producing useless timings.
say "GPU check"
if command -v nvidia-smi >/dev/null; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | sed 's/^/    /'
else
  bad "nvidia-smi missing -- this node may have no GPU"
fi
ollama run "${MODELS%% *}" "hi" >/dev/null 2>&1
PLACEMENT=$(ollama ps 2>/dev/null | tail -n +2)
echo "$PLACEMENT" | sed 's/^/    /'
if echo "$PLACEMENT" | grep -qi "100% gpu"; then
  ok "running on GPU"
else
  bad "NOT fully on GPU -- fix before running the grid, or the numbers are worthless"
  bad "try: nvidia-smi -L   then   export CUDA_VISIBLE_DEVICES=<MIG-UUID>"
  exit 1
fi

# --- 5. launch -------------------------------------------------------------
say "benchmark"
if pgrep -f "benchmark.py" >/dev/null; then
  ok "already running -- not starting a second copy"
else
  # NOTE: an earlier version of this script moved results/benchmark_results.csv
  # aside on first launch, to keep laptop and GPU latencies out of one table.
  # That was wrong twice over: the file is the resume log, so renaming it makes
  # the run redo completed work, and on the first restart after a code change it
  # captured three GPU runs and labelled them as laptop results. The results
  # file is now left alone -- benchmark.py appends and skips what is already
  # there. Separate hardware profiles are made by copying the file by hand
  # before a run, never by this script.
  mkdir -p results
  nohup .venv/bin/python -u benchmark.py --stage a --models $MODELS \
        > "$LOG" 2>&1 &
  sleep 20
  ok "started (pid $!)"
fi

say "first output"
tail -6 "$LOG" 2>/dev/null

cat <<'EOF'

    Monitor:   bash gpu_setup.sh --check
    Live log:  tail -f ~/Web_Scraping_Engine/results/stage_a_gpu.log
    Download:  results/benchmark_results.csv   <- the only file that matters

    If the session drops, re-run this script. Completed runs are skipped.
EOF
