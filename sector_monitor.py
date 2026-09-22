import streamlit as st
import akshare as ak
import pandas as pd
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="板块资金监控看板")
st.title("📊 板块资金占比监控（同花顺板块体系）")

# ---------------------- 全局参数区域 ----------------------
st.sidebar.header("设置面板")
pred_total_market = st.sidebar.number_input("预测今日大盘全天成交额(亿)", value=10000, min_value=1000, step=500)
highlight_switch = st.sidebar.checkbox("开启重点板块高亮", value=True)
highlight_threshold1 = st.sidebar.slider("橙色高亮阈值(占当前大盘%)", min_value=1.0, max_value=8.0, value=2.5, step=0.1)
highlight_threshold2 = st.sidebar.slider("红色高亮阈值(占当前大盘%)", min_value=3.0, max_value=10.0, value=4.5, step=0.1)
min_amt_filter = st.sidebar.number_input("板块最小成交额过滤(亿)", value=20, min_value=0, step=5)

tab_industry, tab_concept = st.tabs(["行业板块", "概念板块"])

# ---------------------- 计算A股已交易分钟 ----------------------
def get_trade_minutes():
    now = datetime.now()
    h, m = now.hour, now.minute
    # 上午 9:30-11:30 (120min) 下午13:00-15:00 (120min)
    if 9 <= h < 11 or (h ==11 and m <=30):
        if h <9 or (h==9 and m<30):
            return 0
        return (h-9)*60 + m -30
    elif 11 < h <13:
        return 120
    elif 13 <=h <=15:
        if h==15 and m>0:
            return 240
        return 120 + (h-13)*60 + m
    else:
        return 240 # 收盘

trade_min = get_trade_minutes()
total_trade_min = 240
time_ratio = trade_min / total_trade_min if trade_min>0 else 1

# ---------------------- 获取板块数据函数 ----------------------
@st.cache_data(ttl=30) # 30秒刷新一次
def fetch_sector_data(sector_type):
    if sector_type == "industry":
        df = ak.stock_sector_spot(indicator="行业板块")
    else:
        df = ak.stock_sector_spot(indicator="概念板块")
    # 字段清洗 同花顺板块接口
    df = df[["板块名称", "涨跌幅", "成交额"]].copy()
    df["成交额"] = pd.to_numeric(df["成交额"], errors="coerce")
    df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
    df = df.dropna()
    df = df[df["成交额"] >= min_amt_filter]
    return df

# 获取全市场总成交额
@st.cache_data(ttl=30)
def get_market_total_amount():
    stock_df = ak.stock_zh_a_spot_em()
    total_amt = pd.to_numeric(stock_df["成交额"], errors="coerce").sum() / 1e8
    return round(total_amt,2)

market_total = get_market_total_amount()

# ---------------------- 主逻辑计算 ----------------------
def process_df(df):
    df["占当前大盘成交(%)"] = (df["成交额"] / market_total *100).round(2)
    df["占预测全天大盘(%)"] = (df["成交额"] / pred_total_market *100).round(2)
    # 维持上涨预估收盘成交额 & 还需成交
    df["预估收盘板块成交"] = (df["成交额"] / time_ratio).round(2)
    df["维持上涨还需成交(亿)"] = (df["预估收盘板块成交"] - df["成交额"]).round(2)
    df = df.sort_values("占当前大盘成交(%)", ascending=False)
    return df

# 高亮样式
def highlight_row(row):
    if not highlight_switch:
        return [""]*len(row)
    val = row["占当前大盘成交(%)"]
    if val >= highlight_threshold2:
        return ["background-color:#ffcccc"]*len(row)
    elif val >= highlight_threshold1:
        return ["background-color:#fff2cc"]*len(row)
    else:
        return [""]*len(row)

# ---------------------- 渲染Tab ----------------------
with tab_industry:
    st.metric(label="当前全市场总成交额(亿)", value=market_total)
    st.info(f"已交易 {trade_min} / 240 分钟")
    df_ind = fetch_sector_data("industry")
    df_ind = process_df(df_ind)
    # 资金分流提示
    high_count = len(df_ind[df_ind["占当前大盘成交(%)"] >= highlight_threshold2])
    if high_count >=2:
        st.warning(f"⚠️ 存在{high_count}个板块处于高资金占用，资金分流，主线持续性承压，留意止盈！")
    st.dataframe(df_ind.style.apply(highlight_row, axis=1), use_container_width=True)

with tab_concept:
    st.metric(label="当前全市场总成交额(亿)", value=market_total)
    st.info(f"已交易 {trade_min} / 240 分钟")
    df_con = fetch_sector_data("concept")
    df_con = process_df(df_con)
    high_count = len(df_con[df_con["占当前大盘成交(%)"] >= highlight_threshold2])
    if high_count >=2:
        st.warning(f"⚠️ 存在{high_count}个板块处于高资金占用，资金分流，主线持续性承压，留意止盈！")
    st.dataframe(df_con.style.apply(highlight_row, axis=1), use_container_width=True)

st.markdown("""
> 说明：
> 1. 数据来源akshare，盘中延迟约30秒，仅用于学习研究，非交易所实时行情
> 2. 【维持上涨还需成交】是基于当前时间线性外推估算，仅参考，不代表真实资金需求
> 3. 红色=高资金占用；橙色=中等资金占用；可在侧边栏调整阈值
""")
