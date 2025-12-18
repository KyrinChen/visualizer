# Merged Events & SED Caption 功能文档

## 1. 概述

扩展了可视化工具以支持：
- **Merged Events**：形态学合并后的事件数据（包含统计字段）
- **SED Caption**：多版本文本描述（支持 content 和 comment）

---

## 2. Merged Events 处理

### 数据格式
```json
{
  "merged_events": {
    "0.1": {
      "Event Label": [
        {
          "onset": 0.0,
          "offset": 10.0,
          "count": 1,
          "total_span": 10.0,
          "type": "type_b3_ambience"
        },
        {
          "onset": 5.0,
          "offset": 8.0,
          "count": 2,
          "total_span": 3.0,
          "duty_cycle": 0.8,
          "actual_duration": 2.4,
          "type": "type_b2_activities"
        }
      ]
    }
  }
}
```

### 关键字段
- **count**: 合并前的事件数量
- **total_span**: 总时间跨度
- **duty_cycle**: 占空比（0-1，可选）
- **actual_duration**: 实际持续时间（可选）
- **type**: 事件类型（type_a_impulsive, type_b1_operations, type_b2_activities, type_b3_ambience）

### 实现要点
1. **数据源选择**：用户可在"原始"和"合并后"之间切换
2. **默认显示**：优先显示"合并后"数据（如果存在）
3. **动态字段处理**：Timeline tooltip 和表格根据实际存在的字段动态生成
4. **字段格式化**：
   - `duty_cycle`: 百分比显示（如 "80.0%"）
   - `total_span`/`actual_duration`: 时间格式（如 "00:10.000"）
   - `count`: 整数显示

---

## 3. SED Caption 处理

### 数据格式（新格式）
```json
{
  "sed_caption": {
    "v1": {
      "content": "The scene opens with...",
      "comment": "Optional comment text"
    },
    "v2": {
      "content": "Alternative description...",
      "comment": "Another comment"
    }
  }
}
```

### 实现要点

#### 格式兼容性
- **新格式**：`{"v1": {"content": "...", "comment": "..."}}` ✅ 支持
- **旧格式**：`{"v1": "..."}` ✅ 兼容（向后兼容）

#### 多版本切换
- **单个版本**：直接显示 content 和 comment（如果存在）
- **多个版本**：使用 Streamlit tabs 切换（`Version: v1`, `Version: v2`, ...）

#### Comment 显示逻辑
```python
# 关键判断：确保 comment 存在且非空
if comment is not None and str(comment).strip():
    st.text_area("Comment", value=str(comment), ...)
```

**注意**：使用 `is not None and str(comment).strip()` 而非简单的 `if comment:`，避免空字符串或 None 值导致显示问题。

#### UI 布局
- **Content**: 高度 300px 的 text_area
- **Comment**: 高度 200px 的 text_area（仅当存在时显示）

---

## 4. 数据源选择逻辑

### 可用数据源检测
```python
available_sources = []
if output_data:  # 原始数据
    available_sources.append("原始")
if merged_data:  # 合并后数据
    available_sources.append("合并后")
```

### 默认选择策略
```python
# 优先显示"合并后"（如果存在），否则显示"原始"
default_index = 1 if "合并后" in available_sources else 0
```

---

## 5. 字段格式化配置

### FIELD_FORMAT_CONFIG
集中管理字段格式化规则：
- **时间字段**（onset, offset, duration, total_span, actual_duration）：毫秒精度（`%H:%M:%S.%L`）
- **百分比字段**（duty_cycle）：百分比格式（`format(datum.DutyCycle * 100, '.1f') + '%'`）
- **整数字段**（count）：整数格式（`.0f`）

### 动态字段处理
- Timeline tooltip：根据 DataFrame 实际列动态生成
- 表格显示：只显示存在的字段，不添加计算字段（如不计算 Duration 如果已有 duration 或 total_span）
- Null 值处理：使用 Altair `isValid()` 函数，缺失字段显示 "None"

---

## 6. 常见问题排查

### Comment 不显示
1. **检查数据格式**：确认是 `{"v1": {"content": "...", "comment": "..."}}` 而非 `{"v1": "..."}`
2. **清除缓存**：重启 Streamlit 应用，或强制刷新浏览器（Ctrl+Shift+R）
3. **验证数据**：使用测试脚本检查 JSON 中 comment 字段是否存在且非空

### 字段显示异常
1. **检查字段名**：确认使用 snake_case（如 `duty_cycle`）而非 camelCase
2. **验证数据**：确认字段在 JSONL 中确实存在
3. **查看控制台**：检查是否有 JavaScript 错误

---

## 7. 测试数据

### 参考文件
- `SED/PretrainedSED/jqchen-test/output/test/SED-test.jsonl`：包含 v1 和 v2 版本的 caption（v2 有 comment）

### 验证脚本
```python
# 检查所有 JSONL 文件中 sed_caption 格式
python3 -c "
import json
from pathlib import Path
# ... 检查逻辑
"
```

---

**文档版本**: v1.0  
**最后更新**: 2025-01-XX

