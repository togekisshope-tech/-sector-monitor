# 安装依赖
!pip install -q streamlit akshare pandas plotly
# 写入app.py（低位三倍量 + 板块选择，增加K线生命线标记）
%%writefile app.py
import streamlit as st
import akshare as ak
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="复盘选股｜低位三倍量", layout="wide")
st.title("盘后复盘选股工具 — 低位横盘三倍量策略")

# 缓存数据
@st.cache_data(ttl=3600*6)
def get_all_stock_spot():
    df = ak.stock_zh_a_spot_em()
    df = df[['代码','名称','最新价','涨跌幅','成交量','成交额','换手率','市盈率-动态','总市值','所属行业']]
    df['总市值'] = pd.to_numeric(df['总市值'], errors='coerce')
    df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
    df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
    df = df[~df['名称'].str.contains("ST", na=False)]
    return df

@st.cache_data(ttl=3600*6)
def get_industry_list():
    df = ak.stock_board_industry_name_em()
    industry_list = df['板块名称'].tolist()
    industry_list.insert(0, "全市场")
    return industry_list

@st.cache_data(ttl=3600*6)
def get_stock_hist(symbol, period=120):
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
    df = df.tail(period).copy()
    df['成交量'] = pd.to_numeric(df['成交量'], errors='coerce')
    df['收盘'] = pd.to_numeric(df['收盘'], errors='coerce')
    df['最高'] = pd.to_numeric(df['最高'], errors='coerce')
    df['最低'] = pd.to_numeric(df['最低'], errors='coerce')
    return df

# 侧边栏参数
with st.sidebar:
    st.header("【低位三倍量策略参数】")
    selected_industry = st.selectbox("选择板块", get_industry_list())
    横盘周期 = st.slider("横盘周期(交易日)", 20, 80, 40)
    max_横盘振幅 = st.slider("横盘最大振幅", 1.1, 1.5, 1.3, step=0.01)
    volume_multiple = st.slider("起爆量倍数", 2.0, 4.0, 3.0, step=0.1)
    min_阳线涨幅 = st.slider("起爆阳线最小涨幅%", 1.0, 8.0, 3.0, step=0.5)
    min_total_mv, max_total_mv = st.slider("总市值范围(亿)", 20, 2000, (30, 600))

df_all = get_all_stock_spot()
if selected_industry != "全市场":
    df_pool = df_all[df_all["所属行业"] == selected_industry].copy()
else:
    df_pool = df_all.copy()
df_pool = df_pool[(df_pool["总市值"] >= min_total_mv) & (df_pool["总市值"] <= max_total_mv)]
st.info(f"当前候选池：{selected_industry}，共 {len(df_pool)} 只标的")

# 三倍量逻辑
def check_triple_volume(symbol):
    try:
        hist = get_stock_hist(symbol, period=横盘周期)
        if len(hist) < 横盘周期 * 0.8:
            return None
        high_max = hist['最高'].max()
        low_min = hist['最低'].min()
        amp = high_max / low_min
        if amp > max_横盘振幅:
            return None
        vol_mean = hist['成交量'].mean()
        hist['涨'] = hist['收盘'].pct_change() * 100
        blast = hist[
            (hist['成交量'] >= vol_mean * volume_multiple) &
            (hist['涨'] >= min_阳线涨幅)
        ]
        if len(blast) == 0:
            return None
        blast_row = blast.iloc[-1]
        return {
            "起爆日期": blast_row["date"],
            "起爆成交量": blast_row["成交量"],
            "横盘均量": round(vol_mean, 2),
            "横盘振幅": round(amp, 3),
            "起爆涨幅": round(blast_row["涨"],2),
            "起爆收盘价": blast_row["收盘"]
        }
    except Exception as e:
        return None

result_list = []
progress_bar = st.progress(0)
total = len(df_pool)
for idx, row in df_pool.iterrows():
    code = row["代码"]
    name = row["名称"]
    industry = row["所属行业"]
    mv = row["总市值"]
    res = check_triple_volume(code)
    if res is not None:
        item = {
            "代码": code,
            "名称": name,
            "所属行业": industry,
            "总市值(亿)": mv,** res
        }
        result_list.append(item)
    progress_bar.progress((idx+1)/total)

result_df = pd.DataFrame(result_list)
st.subheader(f"✅ 满足低位三倍量条件：共 {len(result_df)} 只")
if len(result_df)>0:
    st.dataframe(result_df, use_container_width=True)
    csv = result_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("导出CSV复盘清单", csv, "低位三倍量_选股结果.csv")
else:
    st.warning("当前板块没有找到符合条件标的，可以调整参数再试。")

# K线面板，增加起爆生命线
st.divider()
st.subheader("个股K线复盘（起爆阳线生命线）")
input_code = st.text_input("输入股票代码查看日线", value="")
if input_code:
    hist_df = get_stock_hist(input_code, period=120)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist_df["date"], y=hist_df["收盘"], name="收盘价", line_color="#1f77b4"))
    # 查找起爆K线
    hist_tmp = hist_df.copy()
    hist_tmp['涨'] = hist_tmp['收盘'].pct_change() *100
    vol_mean = hist_tmp['成交量'].tail(横盘周期).mean()
    blast = hist_tmp[(hist_tmp['成交量'] >= vol_mean * volume_multiple) & (hist_tmp['涨'] >= min_阳线涨幅)]
    if len(blast)>0:
        blast_row = blast.iloc[-1]
        blast_price = blast_row["收盘"]
        fig.add_hline(y=blast_price, line_dash="dash", line_color="red", annotation_text=f"起爆生命线 {blast_price:.2f}")
    fig.update_layout(title=f"{input_code} 前复权日线", height=500)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(hist_df.tail(20))
