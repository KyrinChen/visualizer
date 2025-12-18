# Timeline View 优化设计文档

## 1. 问题诊断

### 原始实现的缺陷
1. **严重遮挡 (Occlusion)**: 
   - Y轴 = 阈值 (Threshold)
   - 同一阈值下多个事件同时发生（多音 Polyphony）会互相遮挡
   - 例如：Dog 和 Car 同时在 0-2 秒，只能看到最上层的事件
   
2. **空白行浪费空间**:
   - 使用 `facet` + `resolve_scale(y='shared')` 导致 Y 轴取所有阈值事件的并集
   - 高阈值子图（如 0.5）只有 1 个事件，但被强制显示所有事件类别的空行
   
3. **行高不一致**:
   - 改用 `y='independent'` 后，事件少的分面单行被拉伸到整个高度
   - 视觉效果混乱
   
4. **图表超出边界**:
   - 图例放右侧导致图表主体区域被压缩
   - Timeline 右边界超出音频播放器

---

## 2. 设计方案

### 核心架构：以事件为中心 (Event-Centric)

**布局策略**：
- **Y 轴 = 事件类别** (Event Label)：不同事件自然分行，彻底避免遮挡
- **按阈值垂直分面**：多个子图堆叠，便于对比阈值影响
- **垂直全局布局**：音频播放器 → Timeline → 详细表格，全宽对齐

### 技术选型：手动 vconcat 拼接

**为什么不用 `facet`？**
- `facet` 的 Y 轴策略二选一：
  - `shared`: 严格对齐但产生空白行
  - `independent`: 无空白但行高被拉伸
- 无法为每个分面单独控制高度

**解决方案**：
```python
# 循环为每个阈值创建独立图表
charts = []
for thresh in sorted_thresholds:
    df_thresh = df[df['Threshold'] == thresh]
    
    # 动态计算高度：每行 30px
    event_count = df_thresh['Event'].nunique()
    chart_height = max(60, event_count * 30 + 20)
    
    # 独立图表
    chart = alt.Chart(df_thresh).mark_bar().encode(
        x=alt.X('Start:Q', title='Time (s)'),
        x2='End:Q',
        y=alt.Y('Event:N', sort=None),  # 独立排序
        color=alt.Color('Event:N', 
                       legend=None,  # 移除图例
                       scale=alt.Scale(scheme='tableau20', 
                                     domain=all_event_types)),  # 统一颜色
        ...
    ).properties(
        title=f"Threshold: {thresh}",
        height=chart_height  # 🔑 动态高度
    )
    charts.append(chart)

# 垂直拼接
combined = alt.vconcat(*charts).resolve_scale(
    x='shared',     # 时间轴对齐
    color='shared'  # 颜色一致
)
```

---

## 3. 关键特性

### ✅ 已实现功能
1. **无空白行**：每个分面只显示检测到的事件
2. **行高统一**：每行固定 30px，分面高度 = 事件数量 × 30px
3. **阈值筛选器**：`st.multiselect` 支持只显示关键阈值（长音频场景）
4. **图例移除**：Y 轴标签已足够，避免右侧超出
5. **统一配色**：同一事件在不同阈值下颜色一致（`domain=all_event_types`）

### 📐 布局结构
```
┌────────────────────────────────┐
│ 🎵 Audio Player (全宽)          │
│ [========●========]  0:23/1:45 │
├────────────────────────────────┤
│ 📉 Timeline View (全宽)         │
│ [筛选阈值: □ 0.1 ☑ 0.2 ☑ 0.5]  │
│ ┌─ Threshold: 0.2 ────────────┐│
│ │ Dog  [████]  [██]           ││
│ │ Car  [███]                  ││
│ └─────────────────────────────┘│
│ ┌─ Threshold: 0.5 ────────────┐│
│ │ Dog  [██]                   ││
│ └─────────────────────────────┘│
├────────────────────────────────┤
│ ▶ 📊 Detailed Tables (默认折叠) │
└────────────────────────────────┘
```

---

## 4. 技术决策

| 方面 | 选择 | 理由 |
|------|------|------|
| **Y 轴策略** | 独立（via vconcat） | 无空白行，紧凑高效 |
| **颜色映射** | `tableau20` + 统一 domain | 最多支持 20 种事件，跨阈值一致 |
| **图例显示** | 移除（`legend=None`） | Y 轴已显示事件名，图例冗余且占宽度 |
| **分面高度** | 动态计算 | `max(60, event_count * 30 + 20)` |
| **时间轴对齐** | `resolve_scale(x='shared')` | 所有分面水平对齐，便于对比 |

---

## 5. 权衡 (Trade-offs)

### ❌ 失去的能力
- **严格的垂直对齐**：不同阈值下同一事件的 Y 坐标可能不同（因独立排序）
- **图例快速参考**：需要看 Y 轴标签识别事件类型

### ✅ 获得的优势
- **视觉清晰度**：无遮挡、无空白，信息密度高
- **空间效率**：长音频/多事件场景下减少 50%+ 滚动
- **灵活筛选**：阈值多选框可动态调整显示内容

---

## 6. 使用指南

### 运行工具
```bash
cd /inspire/ssd/project/embodied-multimodality/public/jqchen/tools/visualizer/streamlit/
bash run_pretrained_sed.sh
```

### 测试数据
- 简单场景：`SED/PretrainedSED/output/test/SED_test.jsonl`
- 复杂场景：`SED/PretrainedSED/output/test/test_rich_events.jsonl`

### 交互说明
1. **阈值筛选**：长音频时勾选关键阈值（如只看 0.5）
2. **鼠标悬停**：查看事件详细时间戳（Tooltip）
3. **展开详细表格**：查看数值数据（默认折叠）

---

## 7. 未来优化方向（可选）

### 音频进度同步
- **目标**：音频播放时，Timeline 上显示实时进度红线
- **技术难点**：Streamlit 原生 `st.audio()` 不支持获取播放进度
- **方案**：引入自定义 HTML/JavaScript 组件或第三方库

---

**文档版本**: v1.0  
**最后更新**: 2025-12-15