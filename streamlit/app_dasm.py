#!/usr/bin/env python3
"""
DASM 检测结果可视化工具 (Adapted for new structure)
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

# 添加 src 到路径以便导入
sys.path.append(str(Path(__file__).parent)) 
from src.utils import load_jsonl_files, resolve_path, extract_basename, guess_mime

# ==================== 配置 ====================
DEFAULT_INPUT_PATH = "/inspire/ssd/project/embodied-multimodality/public/jqchen/SED/DASM/output/0912_TAC_for_easy_eval/test"

# ==================== DASM 特有辅助函数 ====================

def format_confidence_bar(confidence: float, width: int = 20) -> str:
    """格式化置信度进度条（文本）"""
    filled = int(confidence * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {confidence:.3f}"

def get_confidence_color(confidence: float) -> str:
    """根据置信度返回颜色"""
    if confidence >= 0.8:
        return "🟢"  # 绿色
    elif confidence >= 0.5:
        return "🟡"  # 黄色
    else:
        return "🔴"  # 红色

# ==================== 渲染函数 ====================

def display_entry(entry: dict, idx: int, jsonl_dir: Path):
    """展示单个 DASM 条目"""
    audio_path = entry.get("audio_path", "")
    audio_basename = extract_basename(audio_path) if audio_path else f"Item {idx}"
    
    with st.expander(f"条目 {idx}: {audio_basename}", expanded=False):
        # 1. 音频播放器
        st.markdown("#### 🎵 音频播放")
        if audio_path:
            # 使用新的 resolve_path
            audio_file = resolve_path(audio_path, jsonl_dir)
            
            if audio_file and audio_file.exists():
                mime = guess_mime(audio_file)
                try:
                    st.audio(str(audio_file), format=mime)
                except Exception as e:
                    st.warning(f"无法加载音频: {e}")
            else:
                st.warning(f"音频文件不存在: {audio_path}")
            st.caption(f"路径: `{audio_path}`")
        else:
            st.info("无音频路径信息")
        
        st.markdown("---")
        
        # 2. 检测结果概览
        st.markdown("#### 📊 检测结果概览")
        
        if not entry.get("success", False):
            st.error(f"处理失败: {entry.get('error', '未知错误')}")
            return
        
        detected_events = entry.get("detected_events", [])
        if not detected_events:
            st.info("未检测到任何事件")
        else:
            # 按置信度降序排列
            detected_events_sorted = sorted(
                detected_events,
                key=lambda x: x.get("confidence", 0),
                reverse=True
            )
            
            # 使用 3 列布局展示事件卡片
            cols = st.columns(3)
            for i, event in enumerate(detected_events_sorted):
                col = cols[i % 3]
                with col:
                    event_name = event.get("event", "Unknown")
                    confidence = event.get("confidence", 0)
                    max_activation = event.get("max_time_activation", 0)
                    
                    color_icon = get_confidence_color(confidence)
                    
                    st.markdown(
                        f"""
                        <div style='padding: 10px; border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 5px; margin-bottom: 10px;'>
                            <strong>{color_icon} {event_name}</strong><br>
                            置信度: {format_confidence_bar(confidence)}<br>
                            最大激活: {max_activation:.3f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        
        st.markdown("---")
        
        # 3. 时间戳详情
        st.markdown("#### ⏱️ 时间戳详情")
        
        event_timestamps = entry.get("event_timestamps", {})
        if not event_timestamps:
            st.info("无时间戳信息")
        else:
            table_data = []
            for event_name, segments in event_timestamps.items():
                for segment in segments:
                    table_data.append({
                        "事件名称": event_name,
                        "开始时间 (s)": f"{segment.get('onset', 0):.2f}",
                        "结束时间 (s)": f"{segment.get('offset', 0):.2f}",
                        "持续时间 (s)": f"{segment.get('duration', 0):.2f}",
                        "最大激活值": f"{segment.get('max_activation', 0):.3f}",
                        "平均激活值": f"{segment.get('mean_activation', 0):.3f}",
                    })
            
            if table_data:
                df = pd.DataFrame(table_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("无时间戳数据")
        
        st.markdown("---")
        
        # 4. 可视化图片
        st.markdown("#### 📈 可视化图片")
        
        vis_path = entry.get("visualization_path")
        if vis_path:
            vis_file = resolve_path(vis_path, jsonl_dir)
            if vis_file and vis_file.exists():
                try:
                    st.image(str(vis_file), use_container_width=True)
                    st.caption(f"路径: `{vis_path}`")
                except Exception as e:
                    st.warning(f"无法加载图片: {e}")
            else:
                st.warning(f"可视化图片不存在: {vis_path}")
        else:
            st.info("无可视化图片")


# ==================== 主函数 ====================

def main():
    st.set_page_config(
        page_title="DASM 检测结果查看器",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🎵 DASM 检测结果查看器")
    st.markdown("---")
    
    with st.sidebar:
        st.header("📁 数据源")
        input_path = st.text_input(
            "输入路径（文件或目录）",
            value=DEFAULT_INPUT_PATH
        )
        
        if not input_path:
            st.warning("请输入路径")
            st.stop()
        
        with st.spinner("加载数据中..."):
            datasets = load_jsonl_files(input_path)
        
        if not datasets:
            st.error(f"未找到任何 JSONL 文件: {input_path}")
            st.stop()
        
        dataset_names = sorted(datasets.keys())
        selected_dataset = st.selectbox("选择数据集", dataset_names)
        
        st.markdown("---")
        total_entries = sum(len(entries) for entries in datasets.values())
        current_entries = len(datasets[selected_dataset])
        st.metric("总条目数", total_entries)
        st.metric("当前数据集条目数", current_entries)
    
    entries = datasets[selected_dataset]
    
    if not entries:
        st.warning(f"数据集 '{selected_dataset}' 中没有条目")
        st.stop()
    
    st.header(f"📋 {selected_dataset} ({len(entries)} 条)")
    
    # 路径解析上下文
    input_path_obj = Path(input_path)
    if input_path_obj.is_file():
        base_dir = input_path_obj.parent
    else:
        base_dir = input_path_obj / selected_dataset
        if not base_dir.exists():
            base_dir = input_path_obj
    
    for idx, entry in enumerate(entries, start=1):
        display_entry(entry, idx, base_dir)
    
    st.markdown("---")
    st.caption(f"共 {len(entries)} 条记录")

if __name__ == "__main__":
    main()

