import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import streamlit as st

def extract_basename(file_path: str) -> str:
    """从文件路径提取文件名（不含扩展名）"""
    return os.path.splitext(os.path.basename(file_path))[0]

def guess_mime(path: Path) -> Optional[str]:
    """根据文件扩展名猜测 MIME 类型"""
    suffix = path.suffix.lower()
    if suffix in {".wav"}:
        return "audio/wav"
    if suffix in {".mp3"}:
        return "audio/mp3"
    return None

@st.cache_data(show_spinner=False)
def load_jsonl_file(jsonl_path: Path) -> List[Dict[str, Any]]:
    """加载单个 JSONL 文件"""
    entries = []
    try:
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    st.warning(f"第 {line_no} 行 JSON 解析失败: {e}")
                    continue
    except Exception as e:
        st.error(f"加载文件失败 {jsonl_path}: {e}")
    return entries

@st.cache_data(show_spinner=False)
def load_jsonl_files(input_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    递归加载 JSONL 文件，键名为相对于 input_path 的路径
    """
    input_path_obj = Path(input_path)
    if not input_path_obj.exists():
        return {}
    
    datasets = {}
    
    if input_path_obj.is_file():
        if input_path_obj.suffix == ".jsonl":
            # 单文件模式，key 还是文件名
            datasets[input_path_obj.name] = load_jsonl_file(input_path_obj)
            
    elif input_path_obj.is_dir():
        # 递归模式：扫描所有子目录
        for jsonl_file in sorted(input_path_obj.rglob("*.jsonl")):
            # 计算相对路径，例如 "subdir/file.jsonl"
            try:
                rel_path = jsonl_file.relative_to(input_path_obj)
                key_name = str(rel_path)
            except ValueError:
                # 理论上不应该发生，除非是符号链接指到外面了
                key_name = jsonl_file.name
                
            entries = load_jsonl_file(jsonl_file)
            if entries:
                datasets[key_name] = entries
                
    return datasets

def resolve_path(target_path: str, base_dir: Path) -> Optional[Path]:
    """
    解析文件路径（支持相对路径和绝对路径）
    
    Args:
        target_path: 目标文件路径字符串
        base_dir: 相对路径的参考目录（通常是 jsonl 文件所在目录）
    """
    if not target_path:
        return None
    
    path_str = target_path.strip()
    path_obj = Path(path_str)
    
    # 1. 如果是绝对路径，直接使用
    if path_obj.is_absolute():
        if path_obj.exists():
            return path_obj
    
    # 2. 尝试多种可能的基准路径
    possible_base_paths = [
        base_dir,                   # JSONL 文件所在目录
        base_dir.parent,            # 父目录
        Path.cwd(),                 # 当前工作目录
    ]
    
    # 如果路径以 ./ 开头，去掉它
    clean_path_str = path_str[2:] if path_str.startswith("./") else path_str
    
    for base in possible_base_paths:
        test_path = base / clean_path_str
        if test_path.exists():
            return test_path
            
    # 如果都找不到，且原路径是绝对路径，就返回原路径
    if path_obj.is_absolute():
        return path_obj
        
    return None
