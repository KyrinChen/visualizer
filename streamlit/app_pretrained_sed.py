import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import altair as alt

# 添加 src 到路径以便导入
sys.path.append(str(Path(__file__).parent)) 
from src.utils import load_jsonl_files, resolve_path, extract_basename, guess_mime

# ==================== 配置 ====================
DEFAULT_INPUT_PATH = "/inspire/ssd/project/embodied-multimodality/public/jqchen/SED/PretrainedSED/output"

# ==================== 可视化函数 ====================

def render_timeline(output_data: dict):
    """使用 Altair 绘制多阈值时间轴对比"""
    all_events = []
    
    # 按照阈值排序 (0.1, 0.2, 0.5)
    sorted_thresholds = sorted(output_data.keys(), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)
    
    for thresh in sorted_thresholds:
        events = output_data[thresh]
        for evt in events:
            all_events.append({
                "Threshold": thresh,
                "Event": evt.get("event_label", "Unknown"),
                "Start": evt.get("onset", 0),
                "End": evt.get("offset", 0),
                "Duration": evt.get("offset", 0) - evt.get("onset", 0)
            })
            
    if not all_events:
        st.info("没有足够的数据用于绘制时间轴")
        return

    df = pd.DataFrame(all_events)
    
    # 创建甘特图
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('Start', title='Time (s)'),
        x2='End',
        y=alt.Y('Threshold', title='Confidence Threshold'),
        color=alt.Color('Event', legend=alt.Legend(title="Event Type")),
        tooltip=['Event', 'Start', 'End', 'Duration', 'Threshold']
    ).properties(
        height=300,
        title="Event Timeline by Threshold"
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

def display_entry(entry: dict, idx: int, jsonl_dir: Path):
    """展示单个 PretrainedSED 条目"""
    audio_path_str = entry.get("audio_path", "")
    audio_basename = extract_basename(audio_path_str) if audio_path_str else f"Item {idx}"
    
    with st.expander(f"#{idx} {audio_basename}", expanded=True):
        col1, col2 = st.columns([1, 2])
        
        # 左侧：音频和基本信息
        with col1:
            st.markdown("### 🎵 Audio Source")
            
            real_audio_path = resolve_path(audio_path_str, jsonl_dir)
            
            if real_audio_path and real_audio_path.exists():
                mime = guess_mime(real_audio_path)
                st.audio(str(real_audio_path), format=mime)
                st.success(f"Loaded: `{real_audio_path.name}`")
            else:
                st.error(f"File not found: {audio_path_str}")
                st.caption("Try checking if the path in JSONL is correct or accessible.")
            
            st.markdown("---")
            st.markdown(f"**Raw Path**: `{audio_path_str}`")

        # 右侧：检测结果
        with col2:
            st.markdown("### 📊 Detection Results")
            
            output_data = entry.get("output", {})
            if not output_data:
                st.warning("No detection output found.")
            else:
                # 获取所有阈值并排序
                thresholds = sorted(output_data.keys(), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)
                
                # 创建 Tabs：每个阈值一个 Tab，最后加一个对比 Tab
                tab_labels = [f"Thresh: {t}" for t in thresholds] + ["📉 Timeline View"]
                tabs = st.tabs(tab_labels)
                
                # 渲染每个阈值的列表数据
                for i, thresh in enumerate(thresholds):
                    with tabs[i]:
                        events = output_data[thresh]
                        if not events:
                            st.info(f"No events detected at threshold {thresh}")
                        else:
                            df = pd.DataFrame(events)
                            # 整理列显示顺序
                            cols = ["event_label", "onset", "offset"]
                            # 如果有其他列也显示出来，但放在后面
                            other_cols = [c for c in df.columns if c not in cols and c != "filename"]
                            display_cols = cols + other_cols
                            
                            st.dataframe(
                                df[display_cols].style.format({"onset": "{:.3f}", "offset": "{:.3f}"}),
                                use_container_width=True,
                                hide_index=True
                            )
                
                # 渲染时间轴视图
                with tabs[-1]:
                    render_timeline(output_data)

# ==================== 主程序 ====================

def main():
    st.set_page_config(
        page_title="PretrainedSED Visualizer",
        layout="wide",
        page_icon="🎵"
    )
    
    st.sidebar.title("🛠️ PretrainedSED Visualizer")
    
    # 初始化 session_state
    if 'current_idx' not in st.session_state:
        st.session_state.current_idx = 0
    
    # 1. 侧边栏配置
    input_path_str = st.sidebar.text_input(
        "Data Path (JSONL File/Dir)", 
        value=DEFAULT_INPUT_PATH
    )
    
    if not input_path_str:
        st.info("👈 Please verify the data path in the sidebar.")
        st.stop()
        
    # 2. 加载数据
    with st.spinner("Loading data..."):
        datasets = load_jsonl_files(input_path_str)
        
    if not datasets:
        st.error("No valid JSONL files found.")
        st.stop()
        
    # 3. 增强的文件选择器（支持文件夹筛选）
    all_file_keys = sorted(datasets.keys())
    
    # 提取所有包含文件的子目录
    subdirs = set()
    for key in all_file_keys:
        p = Path(key)
        # 如果 parent 不是 . 说明有子目录
        if p.parent != Path("."):
            subdirs.add(str(p.parent))
            
    # 如果有子目录，提供目录筛选器
    selected_subdir = "All"
    if subdirs:
        subdir_options = ["All"] + sorted(list(subdirs))
        selected_subdir = st.sidebar.selectbox("📂 Filter by Folder", subdir_options)
        
    # 根据选择的目录过滤文件列表
    if selected_subdir == "All":
        filtered_keys = all_file_keys
    else:
        # 只显示该子目录下的文件
        filtered_keys = [k for k in all_file_keys if str(Path(k).parent) == selected_subdir]
        
    if not filtered_keys:
        st.warning(f"No files found in folder: {selected_subdir}")
        st.stop()
        
    selected_dataset_key = st.sidebar.selectbox(
        "📄 Select File", 
        filtered_keys,
        # 如果已经选了特定目录，下拉框里就只显示文件名，简洁一点
        format_func=lambda x: Path(x).name if selected_subdir != "All" else x
    )
    
    entries = datasets[selected_dataset_key]
    
    # 重置索引：如果切换了文件，可能当前索引越界，重置为 0
    if 'last_dataset_key' not in st.session_state or st.session_state.last_dataset_key != selected_dataset_key:
        st.session_state.current_idx = 0
        st.session_state.last_dataset_key = selected_dataset_key
    
    # 4. 条目导航控制
    total_entries = len(entries)
    st.sidebar.markdown("---")
    st.sidebar.metric("Total Items", total_entries)
    
    if total_entries > 0:
        # 下拉选择框：格式化为 "Idx: Filename"
        def format_entry_option(idx):
            entry = entries[idx]
            audio_path = entry.get("audio_path", "")
            name = Path(audio_path).name if audio_path else f"Item {idx+1}"
            return f"{idx+1}: {name}"
        
        # 回调函数：处理按钮点击
        def update_index_by_button(delta):
            new_idx = st.session_state.current_idx + delta
            if 0 <= new_idx < total_entries:
                st.session_state.current_idx = new_idx
                # 关键：必须显式更新 Selectbox 绑定的 key，否则 Selectbox 不会变
                # 注意：key 'item_selector' 直接存储的是 value (即 index)
                # 因为 options=range(total_entries)，所以 value 就是 index
                st.session_state.item_selector = new_idx

        # 核心逻辑：Selectbox 和 Session State 绑定
        def on_selectbox_change():
            st.session_state.current_idx = st.session_state.item_selector

        # 下拉框：绑定 key 和 on_change
        st.sidebar.selectbox(
            "Select Audio Item",
            options=range(total_entries),
            format_func=format_entry_option,
            index=st.session_state.current_idx,
            key='item_selector',
            on_change=on_selectbox_change
        )
        
        # 翻页按钮：使用 callback
        col_prev, col_next = st.sidebar.columns(2)
        with col_prev:
            st.button(
                "⬅️ Prev", 
                disabled=st.session_state.current_idx <= 0,
                on_click=update_index_by_button,
                args=(-1,)
            )
                
        with col_next:
            st.button(
                "Next ➡️", 
                disabled=st.session_state.current_idx >= total_entries - 1,
                on_click=update_index_by_button,
                args=(1,)
            )

        # 5. 显示当前条目
        current_entry = entries[st.session_state.current_idx]
        
        st.title(f"📂 {selected_dataset_key}")
        
        # 计算 base_dir 用于解析相对路径
        input_path_obj = Path(input_path_str)
        if input_path_obj.is_file():
            base_dir = input_path_obj.parent
        else:
            base_dir = (input_path_obj / selected_dataset_key).parent
                
        display_entry(current_entry, st.session_state.current_idx + 1, base_dir)

if __name__ == "__main__":
    main()
