#!/bin/bash
# 自动获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 设置 PYTHONPATH 以便能找到 src
export PYTHONPATH=$PYTHONPATH:$SCRIPT_DIR

echo "Starting PretrainedSED Visualizer..."
echo "Workdir: $SCRIPT_DIR"

streamlit run "$SCRIPT_DIR/app_pretrained_sed.py" --server.port 8502 --server.address 0.0.0.0 --server.fileWatcherType none

