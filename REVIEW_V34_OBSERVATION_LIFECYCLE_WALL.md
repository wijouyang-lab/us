# V34 Observation 生命周期 + Wall 标识修复

## Wall
- OI 可用：Call/Put Wall = 最大 Open Interest 执行价。
- OI 不可用：只显示成交量代理，不再标成“非OI Wall”这种容易误解的表述；邮件显示为“成交量代理；OI不可用”。

## Observation
当前 Observation 不再无限期跟踪。自动结束条件：
- +10%：TARGET_REACHED
- -6%：THESIS_INVALIDATED
- 满 10 个交易日：MAX_TRACKING_SESSIONS
- 同一标的出现新的 Observation：SUPERSEDED_BY_NEW_OBSERVATION
- 同一标的升级为 Core：SUPERSEDED_BY_CORE

结束事件：
- trade_history.csv 写入 Status=Observation_Closed、Exit_Date、Exit_Price、Observation_End_Reason
- 仍参与历史 KPI 完成样本
- 不再进入当前 Observation 跟踪列表
