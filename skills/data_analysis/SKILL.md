# Data Analysis Skill

## Goal
用可复现的计算完成数据分析，而不是口头估算。

## Recommended Workflow
1. 明确指标、时间范围和对比口径
2. 列出需要计算的字段与公式
3. 用 Python 读取或构造数据
4. 打印中间结果，避免 silently 出错
5. 核对单位、缺失值和异常值
6. 输出结论，并附上关键数字

## Tool Policy
- python_repl / python_repl_tool：唯一执行工具
- 金融行情优先使用 yfinance
- 用 print(...) 展示结果
- 不要用 web_search 代替计算

## Quality Rules
- 数字必须来自代码输出
- 说明口径和假设
- 对空值或缺失输入要显式处理
- 结论和计算步骤分开写
