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

def build_tooltip(df: pd.DataFrame, has_merged_fields: bool) -> list:
    """根据是否有合并字段构建 tooltip"""
    tooltip = [
        alt.Tooltip('Event:N', title='Event'),
        alt.Tooltip('StartLabel:N', title='Start'),
        alt.Tooltip('EndLabel:N', title='End'),
        alt.Tooltip('DurationLabel:N', title='Duration'),
        alt.Tooltip('Threshold:N', title='Threshold')
    ]
    
    if has_merged_fields:
        if 'Type' in df.columns:
            tooltip.append(alt.Tooltip('Type:N', title='Type'))
        if 'Count' in df.columns:
            tooltip.append(alt.Tooltip('Count:Q', title='Count', format='.0f'))
        if 'DutyCycle' in df.columns:
            tooltip.append(alt.Tooltip('DutyCycleLabel:N', title='Duty Cycle'))
            tooltip.append(alt.Tooltip('TotalSpanLabel:N', title='Total Span'))
            tooltip.append(alt.Tooltip('ActualDurationLabel:N', title='Actual Duration'))
    
    return tooltip


def build_merged_field_transforms(df: pd.DataFrame, has_merged_fields: bool) -> dict:
    """构建合并字段的格式化转换"""
    transforms = {}
    
    if has_merged_fields and 'DutyCycle' in df.columns:
        # duty_cycle 转换为百分比
        transforms['DutyCycleLabel'] = "format(datum.DutyCycle * 100, '.1f') + '%'"
        # total_span 和 actual_duration 格式化为时间
        transforms['TotalSpanLabel'] = "timeFormat(datum.TotalSpan * 1000, datum.TotalSpan >= 3600 ? '%H:%M:%S' : '%M:%S')"
        transforms['ActualDurationLabel'] = "timeFormat(datum.ActualDuration * 1000, datum.ActualDuration >= 3600 ? '%H:%M:%S' : '%M:%S')"
    
    return transforms


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
    
    # 检测是否有合并后的统计字段（用于决定 tooltip 显示）
    has_merged_fields = False
    sample_event = None
    for thresh in sorted_thresholds:
        events_dict = output_data[thresh]
        for event_label, event_list in events_dict.items():
            if event_list:
                sample_event = event_list[0]
                if "type" in sample_event or "count" in sample_event:
                    has_merged_fields = True
                break
        if has_merged_fields:
            break
    
    for thresh in sorted_thresholds:
        events_dict = output_data[thresh]
        # 格式：{event_label: [{onset, offset, ...}, ...]}
        for event_label, event_list in events_dict.items():
            for evt in event_list:
                event_data = {
                    "Threshold": thresh,  # 保留原始阈值用于分组
                    "Event": event_label,
                    "Start": evt.get("onset", 0),
                    "End": evt.get("offset", 0),
                    "Duration": evt.get("offset", 0) - evt.get("onset", 0)
                }
                # 如果有合并后的统计字段，添加到数据中
                if has_merged_fields:
                    if "type" in evt:
                        event_data["Type"] = evt["type"]
                    if "count" in evt:
                        event_data["Count"] = evt["count"]
                    if "duty_cycle" in evt:
                        event_data["DutyCycle"] = evt["duty_cycle"]
                        event_data["TotalSpan"] = evt.get("total_span", 0)
                        event_data["ActualDuration"] = evt.get("actual_duration", 0)
                all_events.append(event_data)
            
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
            x=alt.X(
                'Start:Q',
                title='Time (s)' if thresh == sorted_thresholds[-1] else '',  # 只在最后一个显示标题
                axis=alt.Axis(
                    grid=True,
                    labelAngle=0,
                    # 始终显示分钟位（不足1分钟显示 00:SS），去掉毫秒
                    labelExpr="timeFormat(datum.value * 1000, datum.value >= 3600 ? '%H:%M:%S' : '%M:%S')"
                )
            ),
            x2='End:Q',
            y=alt.Y(
                'Event:N',
                title='Event Type',
                sort=None,  # 每个分面独立排序
                axis=alt.Axis(labelLimit=200)
            ),
            color=alt.Color(
                'Event:N',
                legend=None,  # 移除图例，避免超出边界
                scale=alt.Scale(scheme='tableau20', domain=all_event_types)  # 统一颜色映射
            ),
            tooltip=build_tooltip(df_thresh, has_merged_fields)
        )
        
        # 构建 transform_calculate 的参数
        calc_transforms = {
            # 始终显示分钟位（不足1分钟显示 00:SS），去掉毫秒
            "StartLabel": "timeFormat(datum.Start * 1000, datum.Start >= 3600 ? '%H:%M:%S' : '%M:%S')",
            "EndLabel": "timeFormat(datum.End * 1000, datum.End >= 3600 ? '%H:%M:%S' : '%M:%S')",
            "DurationLabel": "timeFormat(datum.Duration * 1000, datum.Duration >= 3600 ? '%H:%M:%S' : '%M:%S')"
        }
        # 添加合并字段的格式化转换
        calc_transforms.update(build_merged_field_transforms(df_thresh, has_merged_fields))
        chart = chart.transform_calculate(**calc_transforms).properties(
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
        
        # 第二部分：数据源选择（公共区域）
        output_data = entry.get("output", {})
        merged_data = entry.get("merged_events", {})
        
        # 检查可用数据源
        available_sources = []
        if output_data:
            available_sources.append("原始")
        if merged_data:
            available_sources.append("合并后")
        
        if not available_sources:
            st.warning("No detection data found.")
        else:
            # 数据源选择器（公共，在 Audio Source 和 Timeline View 之间）
            st.markdown("### ⚙️ Data Source")
            col_source1, col_source2 = st.columns([1, 3])
            with col_source1:
                data_source = st.radio(
                    "选择数据源",
                    options=available_sources,
                    index=0,
                    key=f"data_source_{idx}",
                    help="原始：未处理的检测结果\n合并后：按事件形态学合并的结果"
                )
            
            # 根据选择的数据源获取数据
            if data_source == "合并后":
                display_data = merged_data
                data_label = "🔀 Merged Events"
            else:  # "原始"
                display_data = output_data
                data_label = "📉 Original Events"
            
            # 获取阈值列表
            thresholds = sorted(display_data.keys(), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)
            
            st.markdown("---")
            
            # 第三部分：时间轴视图（全宽）
            st.markdown("### 📉 Timeline View")
            
            # 阈值选择器
            selected_thresholds = st.multiselect(
                "选择要显示的阈值",
                options=thresholds,
                default=thresholds,
                key=f"threshold_filter_{idx}_{data_source}",
                help="长音频时可以只选择关键阈值，减少滚动"
            )
            
            # 渲染时间轴
            if selected_thresholds:
                render_timeline(display_data, selected_thresholds)
            else:
                st.info("👆 请至少选择一个阈值以显示时间轴")
            
            st.markdown("---")
            
            # 第四部分：详细数据表格（折叠在 Tabs 中）
            with st.expander(f"📊 Detailed Results ({data_source})", expanded=False):
                # 创建 Tabs：每个阈值一个 Tab
                tab_labels = [f"Thresh: {t}" for t in thresholds]
                tabs = st.tabs(tab_labels)
                
                # 渲染每个阈值的列表数据
                for i, thresh in enumerate(thresholds):
                    with tabs[i]:
                        events_dict = display_data[thresh]
                        # 格式：{event_label: [{onset, offset, ...}, ...]}
                        events_list = []
                        for event_label, event_list in events_dict.items():
                            for evt in event_list:
                                event_row = {
                                    "event_label": event_label,
                                    "onset": evt.get("onset", 0),
                                    "offset": evt.get("offset", 0)
                                }
                                # 如果是合并后的数据，添加额外字段
                                if data_source == "合并后":
                                    if "type" in evt:
                                        event_row["type"] = evt["type"]
                                    if "count" in evt:
                                        event_row["count"] = evt["count"]
                                    if "duty_cycle" in evt:
                                        event_row["duty_cycle"] = evt["duty_cycle"]
                                        event_row["total_span"] = evt.get("total_span", 0)
                                        event_row["actual_duration"] = evt.get("actual_duration", 0)
                                events_list.append(event_row)
                        
                        if not events_list:
                            st.info(f"No events detected at threshold {thresh}")
                        else:
                            df = pd.DataFrame(events_list)
                            
                            # 根据数据源确定列显示顺序和格式
                            if data_source == "合并后":
                                # 合并后数据：显示更多字段
                                base_cols = ["event_label", "onset", "offset", "type", "count"]
                                # 检查是否有 duty_cycle（Type B 才有）
                                if "duty_cycle" in df.columns:
                                    extra_cols = ["duty_cycle", "total_span", "actual_duration"]
                                else:
                                    extra_cols = []
                                display_cols = base_cols + extra_cols
                                
                                # 格式化规则
                                format_dict = {
                                    "onset": "{:.3f}",
                                    "offset": "{:.3f}",
                                    "duty_cycle": "{:.3f}",
                                    "total_span": "{:.3f}",
                                    "actual_duration": "{:.3f}"
                                }
                            else:
                                # 原始数据：只显示基础字段
                                display_cols = ["event_label", "onset", "offset"]
                                format_dict = {"onset": "{:.3f}", "offset": "{:.3f}"}
                            
                            # 只显示存在的列
                            display_cols = [c for c in display_cols if c in df.columns]
                            
                            st.dataframe(
                                df[display_cols].style.format(format_dict),
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
        
    # 数据刷新按钮：清除缓存并重新运行，确保新文件被加载
    if st.sidebar.button("🔄 Refresh data (clear cache)", help="清除缓存并重新加载数据文件"):
        try:
            st.cache_data.clear()
        except Exception:
            pass
        try:
            st.experimental_memo.clear()
        except Exception:
            pass
        # Streamlit ≥1.30 使用 st.rerun；兼容旧版本则保留回退
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()
        
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
