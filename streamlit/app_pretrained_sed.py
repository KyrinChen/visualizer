import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import altair as alt

# 添加 src 到路径以便导入
sys.path.append(str(Path(__file__).parent)) 
from src.utils import load_jsonl_files, resolve_path, extract_basename, guess_mime

# ==================== 配置 ====================
DEFAULT_INPUT_PATH = "/inspire/ssd/project/embodied-multimodality/public/jqchen/SED/PretrainedSED/jqchen-test/output"

# 基础字段常量
BASE_FIELDS = {"onset", "offset", "event_label"}
TIME_FIELDS = ["onset", "offset", "duration", "total_span", "actual_duration", "duty_cycle"]

# 字段格式化配置（从现有代码逻辑抽取，保持一致性）
FIELD_FORMAT_CONFIG = {
    "type": {
        "tooltip_type": "N",  # Type:N (文本)
        "table_format": None  # 表格中不格式化（文本）
    },
    "count": {
        "tooltip_type": "Q",
        "tooltip_format": ".0f",  # Count:Q, format='.0f' (整数)
        "table_format": "{:.0f}"
    },
    "duty_cycle": {
        "tooltip_type": "N",  # DutyCycleLabel:N
        "transform": "format(datum.DutyCycle * 100, '.1f') + '%'",  # 百分比，1位小数
        "table_format": "{:.3f}"  # 表格中3位小数
    },
    "total_span": {
        "tooltip_type": "N",  # TotalSpanLabel:N
        "transform": "timeFormat(datum.TotalSpan * 1000, datum.TotalSpan >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
        "table_format": "{:.3f}"
    },
    "actual_duration": {
        "tooltip_type": "N",  # ActualDurationLabel:N
        "transform": "timeFormat(datum.ActualDuration * 1000, datum.ActualDuration >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
        "table_format": "{:.3f}"
    },
    "duration": {
        "tooltip_type": "N",  # DurationLabel:N (如果数据中有 duration 字段)
        "transform": "timeFormat(datum.Duration * 1000, datum.Duration >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
        "table_format": "{:.3f}"
    },
    "onset": {
        "transform": "timeFormat(datum.Start * 1000, datum.Start >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
        "table_format": "{:.3f}"
    },
    "offset": {
        "transform": "timeFormat(datum.End * 1000, datum.End >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
        "table_format": "{:.3f}"
    },
}

# 字段显示优先级（用于表格列排序）
FIELD_PRIORITY = [
    "event_label", "onset", "offset", "type", "count",
    "duration", "total_span", "duty_cycle", "actual_duration"
]


def snake_to_camel(snake_str: str) -> str:
    """将 snake_case 转换为 PascalCase"""
    components = snake_str.split('_')
    return ''.join(word.capitalize() for word in components)


def camel_to_snake(camel_str: str) -> str:
    """将 PascalCase 转换为 snake_case"""
    import re
    snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
    snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', snake)
    return snake.lower()


def format_title(field_name: str) -> str:
    """格式化字段标题（用于 tooltip 和表格）"""
    # 特殊字段的标题映射
    title_map = {
        "duty_cycle": "Duty Cycle",
        "total_span": "Total Span",
        "actual_duration": "Actual Duration",
        "event_label": "Event",
    }
    if field_name in title_map:
        return title_map[field_name]
    # 默认：将 snake_case 转为 Title Case
    return field_name.replace('_', ' ').title()


# ==================== 可视化函数 ====================

def get_valid_fields(df: pd.DataFrame, skip_cols: set = None) -> list:
    """获取 DataFrame 中有效的字段（非空值占比 > 0）"""
    if skip_cols is None:
        skip_cols = {'Threshold', 'Event', 'Start', 'End'}
    
    valid_fields = []
    for col in sorted(df.columns):
        if col in skip_cols:
            continue
        if df[col].notna().sum() > 0:  # 至少有一个非空值
            valid_fields.append(col)
    return valid_fields


def build_tooltip(df: pd.DataFrame) -> list:
    """动态构建 tooltip，显示所有字段，空值显示为 null"""
    tooltip = [
        alt.Tooltip('Event:N', title='Event'),
        alt.Tooltip('StartLabel:N', title='Start'),
        alt.Tooltip('EndLabel:N', title='End'),
        alt.Tooltip('Threshold:N', title='Threshold')
    ]
    
    # 获取所有可能的字段（包括可能为空的字段）
    skip_cols = {'Threshold', 'Event', 'Start', 'End'}
    all_cols = [col for col in sorted(df.columns) if col not in skip_cols]
    
    # 动态添加所有字段（包括可能为空的），统一使用 Label 字段以支持 null 显示
    for col in all_cols:
        field = camel_to_snake(col)
        config = FIELD_FORMAT_CONFIG.get(field, {})
        
        # 所有字段都使用 Label 版本，以便在 transform 中处理 null 值
        tooltip.append(alt.Tooltip(f'{col}Label:N', title=format_title(field)))
    
    return tooltip


def build_field_transforms(df: pd.DataFrame) -> dict:
    """动态构建字段的格式化转换，空值显示为 null"""
    transforms = {
        "StartLabel": "timeFormat(datum.Start * 1000, datum.Start >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
        "EndLabel": "timeFormat(datum.End * 1000, datum.End >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')",
    }
    
    # 获取所有可能的字段（包括可能为空的字段）
    skip_cols = {'Threshold', 'Event', 'Start', 'End'}
    all_cols = [col for col in df.columns if col not in skip_cols]
    
    # 动态添加所有字段的转换（包括可能为空的）
    for col in all_cols:
        field = camel_to_snake(col)
        config = FIELD_FORMAT_CONFIG.get(field, {})
        
        if "transform" in config:
            # 使用条件表达式：如果字段有效则格式化，否则显示 "None"
            transform_expr = config["transform"]
            transforms[f'{col}Label'] = f"isValid(datum.{col}) && datum.{col} != null ? ({transform_expr}) : 'None'"
        elif field == "type":
            # type 字段：如果有效则显示，否则显示 "None"
            transforms[f'{col}Label'] = f"isValid(datum.{col}) && datum.{col} != null ? datum.{col} : 'None'"
        elif config.get("tooltip_format"):
            # 数值字段（如 count）：如果有效则格式化，否则显示 "None"
            format_str = config["tooltip_format"]
            transforms[f'{col}Label'] = f"isValid(datum.{col}) && datum.{col} != null ? format(datum.{col}, '{format_str}') : 'None'"
        else:
            # 其他字段：如果有效则显示，否则显示 "None"
            transforms[f'{col}Label'] = f"isValid(datum.{col}) && datum.{col} != null ? String(datum.{col}) : 'None'"
    
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
    
    for thresh in sorted_thresholds:
        events_dict = output_data[thresh]
        # 格式：{event_label: [{onset, offset, ...}, ...]}
        for event_label, event_list in events_dict.items():
            for evt in event_list:
                event_data = {
                    "Threshold": thresh,
                    "Event": event_label,
                    "Start": evt.get("onset", 0),
                    "End": evt.get("offset", 0),
                }
                
                # 动态添加原始数据中的所有字段（除了基础字段）
                for key, value in evt.items():
                    if key not in BASE_FIELDS:
                        event_data[snake_to_camel(key)] = value
                
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
        chart_height = max(60, event_count * 30 + 20)
        
        # 创建图表
        calc_transforms = build_field_transforms(df_thresh)
        chart = alt.Chart(df_thresh).mark_bar(opacity=0.8).encode(
            x=alt.X(
                'Start:Q',
                title='Time (s)' if thresh == sorted_thresholds[-1] else '',
                axis=alt.Axis(
                    grid=True,
                    labelAngle=0,
                    labelExpr="timeFormat(datum.value * 1000, datum.value >= 3600 ? '%H:%M:%S.%L' : '%M:%S.%L')"
                )
            ),
            x2='End:Q',
            y=alt.Y(
                'Event:N',
                title='Event Type',
                sort=None,
                axis=alt.Axis(labelLimit=200)
            ),
            color=alt.Color(
                'Event:N',
                legend=None,
                scale=alt.Scale(scheme='tableau20', domain=all_event_types)
            ),
            tooltip=build_tooltip(df_thresh)
        ).transform_calculate(**calc_transforms).properties(
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
            # 默认选择"合并后"（如果存在），否则选择"原始"
            default_index = 1 if "合并后" in available_sources else 0
            
            st.markdown("### ⚙️ Data Source")
            col_source1, col_source2 = st.columns([1, 3])
            with col_source1:
                data_source = st.radio(
                    "选择数据源",
                    options=available_sources,
                    index=default_index,
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
            
            # 新增：文本内容显示部分
            format_text_data = entry.get("format_text", {})
            sed_caption_data = entry.get("sed_caption", {})
            
            if format_text_data:
                st.markdown("### 📄 Format Text")
                # 按阈值排序
                format_thresholds = sorted(format_text_data.keys(), 
                                          key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0)
                
                if len(format_thresholds) == 1:
                    st.text_area(
                        f"Threshold: {format_thresholds[0]}",
                        value=format_text_data[format_thresholds[0]],
                        height=300,
                        key=f"format_text_{idx}",
                        disabled=True
                    )
                else:
                    # 多个阈值，使用 tabs
                    format_tabs = st.tabs([f"Thresh: {t}" for t in format_thresholds])
                    for i, thresh in enumerate(format_thresholds):
                        with format_tabs[i]:
                            st.text_area(
                                "Text Content",
                                value=format_text_data[thresh],
                                height=300,
                                key=f"format_text_{idx}_{thresh}",
                                disabled=True
                            )
                st.markdown("---")
            
            if sed_caption_data:
                st.markdown("### ✍️ SED Caption")
                # 按版本排序
                versions = sorted(sed_caption_data.keys())
                
                # 辅助函数：提取 caption 的 content 和 comment
                def extract_caption_data(version_data):
                    """提取 caption 数据
                    支持新格式：{"v1": {"content": "...", "comment": "..."}}
                    兼容旧格式：{"v1": "..."} (直接字符串)
                    返回: (content, comment) 元组，comment 可能为 None
                    """
                    if isinstance(version_data, dict):
                        # 新格式：{"content": "...", "comment": "..."}
                        content = version_data.get("content", "")
                        comment = version_data.get("comment")  # 可能为 None
                        return content, comment
                    elif isinstance(version_data, str):
                        # 旧格式：直接字符串
                        return version_data, None
                    else:
                        # 降级处理：尝试转换为字符串
                        return str(version_data), None
                
                if len(versions) == 1:
                    # 单个版本：直接显示
                    version = versions[0]
                    content, comment = extract_caption_data(sed_caption_data[version])
                    
                    st.text_area(
                        f"Version: {version} - Content",
                        value=content,
                        height=300,
                        key=f"sed_caption_content_{idx}_{version}",
                        disabled=True
                    )
                    
                    # 如果有 comment，显示它（检查是否为 None 且非空字符串）
                    if comment is not None and str(comment).strip():
                        st.text_area(
                            f"Version: {version} - Comment",
                            value=str(comment),
                            height=200,
                            key=f"sed_caption_comment_{idx}_{version}",
                            disabled=True
                        )
                else:
                    # 多个版本，使用 tabs 切换
                    caption_tabs = st.tabs([f"Version: {v}" for v in versions])
                    for i, version in enumerate(versions):
                        with caption_tabs[i]:
                            content, comment = extract_caption_data(sed_caption_data[version])
                            
                            st.text_area(
                                "Content",
                                value=content,
                                height=300,
                                key=f"sed_caption_content_{idx}_{version}",
                                disabled=True
                            )
                            
                            # 如果有 comment，显示它（检查是否为 None 且非空字符串）
                            if comment is not None and str(comment).strip():
                                st.text_area(
                                    "Comment",
                                    value=str(comment),
                                    height=200,
                                    key=f"sed_caption_comment_{idx}_{version}",
                                    disabled=True
                                )
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
                                # 动态添加所有字段（除了基础字段）
                                for key, value in evt.items():
                                    if key not in ["onset", "offset", "event_label"]:
                                        event_row[key] = value
                                events_list.append(event_row)
                        
                        if not events_list:
                            st.info(f"No events detected at threshold {thresh}")
                        else:
                            df = pd.DataFrame(events_list)
                            
                            # 动态构建显示列（按优先级排序）
                            display_cols = []
                            # 按优先级添加存在的字段
                            for field in FIELD_PRIORITY:
                                if field in df.columns:
                                    display_cols.append(field)
                            # 添加其他字段（按字母顺序）
                            other_cols = sorted([col for col in df.columns if col not in display_cols])
                            display_cols.extend(other_cols)
                            
                            # 动态构建格式化规则
                            format_dict = {}
                            for col in display_cols:
                                config = FIELD_FORMAT_CONFIG.get(col, {})
                                if config.get("table_format"):
                                    format_dict[col] = config["table_format"]
                                elif col in TIME_FIELDS:
                                    format_dict[col] = "{:.3f}"  # 默认时间/数字字段3位小数
                            
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
    
    # 根据是否有子目录决定筛选逻辑
    selected_subdir = None
    if subdirs:
        # 有子目录：显示文件夹筛选器，默认选择第一个
        subdir_options = sorted(list(subdirs))
        selected_subdir = st.sidebar.selectbox(
            "📂 Filter by Folder",
            subdir_options,
            index=0  # 默认第一个文件夹
        )
        # 只显示该子目录下的文件
        filtered_keys = [k for k in all_file_keys if str(Path(k).parent) == selected_subdir]
    else:
        # 无子目录：不显示文件夹筛选器，显示所有文件
        filtered_keys = all_file_keys
    
    if not filtered_keys:
        if selected_subdir:
            st.warning(f"No files found in folder: {selected_subdir}")
        else:
            st.warning("No files found.")
        st.stop()
    
    # 文件选择器：默认选择第一个文件
    selected_dataset_key = st.sidebar.selectbox(
        "📄 Select File",
        filtered_keys,
        index=0,  # 默认第一个文件
        # 如果已经选了特定目录，下拉框里就只显示文件名，简洁一点
        format_func=lambda x: Path(x).name if selected_subdir else x
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
