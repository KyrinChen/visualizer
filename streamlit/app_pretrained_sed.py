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

def render_timeline(output_data: dict, selected_thresholds=None):
    """使用 Altair 绘制多阈值时间轴对比（独立分面视图，动态行高）"""
    all_events = []
    
    # 按照阈值排序 (0.1, 0.2, 0.5)
    sorted_thresholds = sorted(output_data.keys(), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)
    
    # 如果指定了筛选阈值，只处理选中的阈值
    if selected_thresholds:
        sorted_thresholds = [t for t in sorted_thresholds if t in selected_thresholds]
    
    if not sorted_thresholds:
        st.warning("请至少选择一个阈值")
        return
    
    for thresh in sorted_thresholds:
        events = output_data[thresh]
        for evt in events:
            all_events.append({
                "Threshold": thresh,  # 保留原始阈值用于分组
                "Event": evt.get("event_label", "Unknown"),
                "Start": evt.get("onset", 0),
                "End": evt.get("offset", 0),
                "Duration": evt.get("offset", 0) - evt.get("onset", 0)
            })
            
    if not all_events:
        st.info("选中的阈值下没有检测到事件")
        return

    df = pd.DataFrame(all_events)
    
    # 获取所有事件类别，用于统一颜色
    all_event_types = sorted(df['Event'].unique())
    
    # 手动为每个阈值创建独立图表
    charts = []
    for thresh in sorted_thresholds:
        # 过滤当前阈值的数据
        df_thresh = df[df['Threshold'] == thresh]
        
        if df_thresh.empty:
            continue
        
        # 计算当前阈值的事件数量，动态调整高度
        event_count = df_thresh['Event'].nunique()
        chart_height = max(60, event_count * 30 + 20)  # 每行30px，保证可读性
        
        # 创建单个图表
        chart = alt.Chart(df_thresh).mark_bar(opacity=0.8).encode(
            x=alt.X('Start:Q', 
                   title='Time (s)' if thresh == sorted_thresholds[-1] else '',  # 只在最后一个显示标题
                   axis=alt.Axis(grid=True, labelAngle=0)),
            x2='End:Q',
            y=alt.Y('Event:N', 
                   title='Event Type',
                   sort=None,  # 每个分面独立排序
                   axis=alt.Axis(labelLimit=200)),
            color=alt.Color('Event:N', 
                           legend=None,  # 移除图例，避免超出边界
                           scale=alt.Scale(scheme='tableau20', domain=all_event_types)),  # 统一颜色映射
            tooltip=[
                alt.Tooltip('Event:N', title='Event'),
                alt.Tooltip('Start:Q', title='Start (s)', format='.2f'),
                alt.Tooltip('End:Q', title='End (s)', format='.2f'),
                alt.Tooltip('Duration:Q', title='Duration (s)', format='.2f'),
                alt.Tooltip('Threshold:N', title='Threshold')
            ]
        ).properties(
            title=f"Threshold: {thresh}",
            height=chart_height
        )
        
        charts.append(chart)
    
    # 垂直拼接所有图表
    if len(charts) == 1:
        combined = charts[0]
    else:
        combined = alt.vconcat(*charts).resolve_scale(
            x='shared',  # 时间轴对齐
            color='shared'  # 颜色一致
        )
    
    st.altair_chart(combined, use_container_width=True)
    
    # 添加说明文字
    st.caption("💡 每个子图代表一个阈值。每行高度统一，事件类型按字母排序。")

def display_entry(entry: dict, idx: int, jsonl_dir: Path):
    """展示单个 PretrainedSED 条目"""
    audio_path_str = entry.get("audio_path", "")
    audio_basename = extract_basename(audio_path_str) if audio_path_str else f"Item {idx}"
    
    with st.expander(f"#{idx} {audio_basename}", expanded=True):
        # 垂直布局：音频 -> 时间轴 -> 详细表格
        
        # 第一部分：音频播放器（全宽）
        st.markdown("### 🎵 Audio Source")
        real_audio_path = resolve_path(audio_path_str, jsonl_dir)
        
        if real_audio_path and real_audio_path.exists():
            mime = guess_mime(real_audio_path)
            st.audio(str(real_audio_path), format=mime)
            st.success(f"✓ Loaded: `{real_audio_path.name}`")
        else:
            st.error(f"✗ File not found: `{audio_path_str}`")
            st.caption("Try checking if the path in JSONL is correct or accessible.")
        
        st.markdown("---")
        
        # 第二部分：时间轴视图（全宽）
        output_data = entry.get("output", {})
        if not output_data:
            st.warning("No detection output found.")
        else:
            # 获取所有阈值并排序
            thresholds = sorted(output_data.keys(), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)
            
            st.markdown("### 📉 Timeline View")
            
            # 阈值筛选器（多选框）
            col_filter, col_space = st.columns([3, 1])
            with col_filter:
                selected_thresholds = st.multiselect(
                    "选择要显示的阈值",
                    options=thresholds,
                    default=thresholds,
                    key=f"threshold_filter_{idx}",
                    help="长音频时可以只选择关键阈值，减少滚动"
                )
            
            # 渲染时间轴
            if selected_thresholds:
                render_timeline(output_data, selected_thresholds)
            else:
                st.info("👆 请至少选择一个阈值以显示时间轴")
            
            st.markdown("---")
            
            # 第三部分：详细数据表格（折叠在 Tabs 中）
            with st.expander("📊 Detailed Results (Tables)", expanded=False):
                # 创建 Tabs：每个阈值一个 Tab
                tab_labels = [f"Thresh: {t}" for t in thresholds]
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
        
        # 底部：元数据信息
        st.caption(f"**Raw Path**: `{audio_path_str}`")

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
