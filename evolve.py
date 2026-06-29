# -*- coding: utf-8 -*-
import pandas as pd
import os
import json
import anthropic
import datetime

# 严格执行引擎配置：策略回测与迭代需要高强度逻辑推理
EVOLVE_MODEL = 'claude-opus-4-8'

HISTORY_FILE = "trade_history.csv"
EVOLVE_LOG = "strategy_evolution.json"

def calculate_metrics(df):
    total_trades = len(df)
    if total_trades == 0:
        return None
        
    # 模拟计算简易胜率 (假设 Exit_Price > Price 为胜)
    closed_trades = df[df['Status'] == 'Dropped'].copy()
    if closed_trades.empty:
        return {"total": total_trades, "win_rate": "N/A", "msg": "当前无已闭环交易数据。"}
        
    closed_trades['Profit'] = pd.to_numeric(closed_trades['Exit_Price']) - pd.to_numeric(closed_trades['Price'])
    winning_trades = closed_trades[closed_trades['Profit'] > 0]
    
    win_rate = len(winning_trades) / len(closed_trades) * 100
    avg_profit = closed_trades['Profit'].mean()
    
    return {
        "total_closed": len(closed_trades),
        "win_rate": round(win_rate, 2),
        "avg_profit_per_trade": round(avg_profit, 2)
    }

def evolve_strategy(metrics):
    if not metrics or metrics.get('win_rate') == 'N/A':
        print("数据不足，无法开启进化进程。")
        return

    print(f"正在启动 {EVOLVE_MODEL} 模型进行策略自适应优化计算...")
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL")
    )
    
    prompt = f"""
你是一个正在进行自我迭代的量化交易模型。请根据当前的客观统计数据，分析当前的选股策略表现，并输出对主程序 scan.py 的提示词 (Prompt) 的迭代建议。

【当前周期闭环指标】：
- 闭环交易总数：{metrics['total_closed']}
- 历史胜率：{metrics['win_rate']}%
- 单笔平均盈亏绝对值：${metrics['avg_profit_per_trade']}

【指令任务】：
1. 评估当前胜率是否达标（及格线 60%）。
2. 如果胜率偏低，请推测可能的逻辑盲点（如：未充分考虑宏观数据、对某类指标过拟合）。
3. 生成一小段“进化规则”，以便下次可以作为约束条件加入到扫描引擎中。
必须输出 JSON 格式。

{{
    "assessment": "胜率评估简述",
    "identified_flaws": "发现的逻辑缺陷",
    "new_prompt_rule": "生成的1条强力提示词补丁（例如：'严禁在VIX大于25时推荐高β科技股'）"
}}
"""
    try:
        response = client.messages.create(
            model=EVOLVE_MODEL,
            max_tokens=1000,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}]
        )
        
        resp_text = response.content[0].text.strip()
        start_idx = resp_text.find('{')
        end_idx = resp_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            resp_text = resp_text[start_idx:end_idx+1]
            
        evolution_data = json.loads(resp_text)
        evolution_data["date"] = datetime.datetime.now().strftime('%Y-%m-%d')
        evolution_data["win_rate"] = metrics['win_rate']
        
        # 追加保存进化日志
        log_data = []
        if os.path.exists(EVOLVE_LOG):
            with open(EVOLVE_LOG, "r", encoding="utf-8") as f:
                log_data = json.load(f)
                
        log_data.append(evolution_data)
        
        with open(EVOLVE_LOG, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
            
        print("✅ 策略进化完成！新生成的规则补丁：")
        print(f"👉 {evolution_data['new_prompt_rule']}")
        
    except Exception as e:
        print(f"进化引擎运行出错: {e}")

if __name__ == "__main__":
    if not os.path.exists(HISTORY_FILE):
        print("未检测到 trade_history.csv，策略进化中止。")
        exit()
        
    df = pd.read_csv(HISTORY_FILE)

    # ── 新版本标记过滤：Hold_Period / Stop_Loss / Score 三字段缺一不可 ──
    # 旧版本记录缺少这三个字段，视为无效行，不纳入胜率统计与进化分析。
    _INVALID_E = {'', 'n/a', 'nan', 'none'}
    for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
        if _col not in df.columns:
            df[_col] = ''
    _valid_mask_e = (
        df['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_E) &
        df['Stop_Loss'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_E) &
        df['Score'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_E)
    )
    _dropped_e = (~_valid_mask_e).sum()
    if _dropped_e > 0:
        print(f"🗂️ 三字段过滤：剔除 {_dropped_e} 条旧版本/不完整记录，不纳入胜率统计。")
    df = df[_valid_mask_e].copy()

    if df.empty:
        print("⚠️ 过滤后无有效新版本记录，策略进化中止。")
        exit()
    metrics = calculate_metrics(df)
    evolve_strategy(metrics)
