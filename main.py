import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import glob
import os

# 自動偵測編碼（可避免 cp950 錯誤）
def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw = f.read(10000)
    try:
        import chardet
        result = chardet.detect(raw)
        return result['encoding']
    except ImportError:
        return 'utf-8-sig'

# 載入多年份資料
def load_multi_year_csv():
    files = sorted(glob.glob(os.path.join("data", "上市_*.csv")))
    all_dfs = []

    for file in files:
        year = 1911 + int(os.path.basename(file).split('_')[1].split('.')[0])
        encoding = detect_encoding(file)
        df = pd.read_csv(file, encoding=encoding)
        df.columns = df.columns.astype(str).str.strip()

        col_industry = "產業類別"
        col_code = "公司代號"
        col_name = "公司名稱"

        col_avg = [col for col in df.columns if "非擔任主管職務之全時員工資訊-員工薪資-平均數" in col][0]
        col_median = [col for col in df.columns if "非擔任主管職務之全時員工資訊-員工薪資-中位數" in col][0]

        selected_cols = [col_industry, col_code, col_name, col_avg, col_median]
        df = df[selected_cols]

        df[col_avg] = pd.to_numeric(df[col_avg].astype(str).str.replace(",", ""), errors='coerce')
        df[col_median] = pd.to_numeric(df[col_median].astype(str).str.replace(",", ""), errors='coerce')

        df = df.rename(columns={
            col_avg: "非擔任主管職務之全時員工薪資平均數(仟元/人)",
            col_median: "非擔任主管職務之全時員工薪資中位數(仟元/人)"
        })
        df['年度'] = year
        all_dfs.append(df)

    return pd.concat(all_dfs, ignore_index=True)

# 載入資料
df_all = load_multi_year_csv()

# 建立 Dash App
app = Dash(__name__)
app.title = "上市櫃公司薪資揭露儀表板"

app.layout = html.Div([
    html.H1("上市櫃公司薪資揭露儀表板", style={"textAlign": "center"}),

    html.Div([
        dcc.Input(id='search-input', type='text', placeholder='請輸入公司名稱或公司代號', style={"width": "300px", "marginRight": "10px"}),
        html.Button('查詢', id='search-btn'),
    ], style={"textAlign": "center", "marginBottom": "20px"}),

    html.Div(id='company-info', style={"textAlign": "center", "fontSize": 20, "marginBottom": "30px"}),

    html.Div(id='charts-container', children=[], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px", "justifyItems": "center"})
])

@app.callback(
    Output('company-info', 'children'),
    Output('charts-container', 'children'),
    Input('search-btn', 'n_clicks'),
    State('search-input', 'value')
)
def update_dashboard(n_clicks, search_value):
    if not n_clicks or not search_value:
        return "", []

    search_value = search_value.strip()
    df_filtered = df_all[
        (df_all['公司代號'].astype(str).str.strip() == search_value) |
        (df_all['公司名稱'].astype(str).str.contains(search_value, case=False, na=False))
    ]

    if df_filtered.empty:
        return f"查無資料：{search_value}", []

    company = df_filtered.iloc[0]
    company_info = f"公司名稱：{company['公司名稱']}，公司代號：{int(company['公司代號'])}，產業類別：{company['產業類別']}"

    charts = []
    hover_style = {"width": "100%", "height": "400px", "transition": "transform 0.3s", "transform": "scale(1)", "boxShadow": "0 2px 6px rgba(0,0,0,0.1)"}

    def create_bar(title, colname, color):
        if colname not in df_filtered.columns:
            return html.Div(f"無資料欄位：{title}")
        fig = px.bar(
            df_filtered,
            x='年度',
            y=colname,
            labels={"年度": "年度", colname: '仟元/人'},
            title=title,
            text=colname,
            color_discrete_sequence=[color]
        )
        fig.update_traces(
            hovertemplate=f"{title}: %{{y}}<extra></extra>",
            marker_line_width=1.5,
            marker_line_color='black'
        )
        fig.update_layout(
            yaxis=dict(
                range=[0, df_filtered[colname].max() * 1.2],
                tickformat=","),
            yaxis_title="仟元/人"
        )
        return dcc.Graph(figure=fig, style=hover_style)

    charts.append(create_bar("非擔任主管職務之全時員工薪資平均數(仟元/人)", "非擔任主管職務之全時員工薪資平均數(仟元/人)", "#1f77b4"))
    charts.append(create_bar("非擔任主管職務之全時員工薪資中位數(仟元/人)", "非擔任主管職務之全時員工薪資中位數(仟元/人)", "#ff7f0e"))

    # 平均數 vs 中位數（位置交換）
    df_comp = df_filtered[["年度", 
                           "非擔任主管職務之全時員工薪資平均數(仟元/人)", 
                           "非擔任主管職務之全時員工薪資中位數(仟元/人)"]].copy()
    df_comp["差距"] = (df_comp["非擔任主管職務之全時員工薪資平均數(仟元/人)"] - 
                   df_comp["非擔任主管職務之全時員工薪資中位數(仟元/人)"]).abs()

    fig_compare = go.Figure()
    fig_compare.add_trace(go.Bar(
        x=df_comp['年度'],
        y=df_comp['非擔任主管職務之全時員工薪資平均數(仟元/人)'],
        name='平均數',
        marker_color='#1f77b4',
        text=df_comp['差距'],
        textposition='outside'
    ))
    fig_compare.add_trace(go.Bar(
        x=df_comp['年度'],
        y=df_comp['非擔任主管職務之全時員工薪資中位數(仟元/人)'],
        name='中位數',
        marker_color='#ff7f0e'
    ))
    fig_compare.update_layout(
        barmode='group',
        title="平均數 vs 中位數（依年度）",
        yaxis_title="仟元/人",
        yaxis_tickformat=",",
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor='center')
    )
    charts.append(dcc.Graph(figure=fig_compare, style=hover_style))

    # 產業類別薪資排行（中位數）
    latest_year = df_filtered['年度'].max()
    df_latest = df_all[df_all['年度'] == latest_year]
    df_industry = df_latest[df_latest['產業類別'] == company['產業類別']]
    df_top10 = df_industry.sort_values("非擔任主管職務之全時員工薪資中位數(仟元/人)", ascending=False).head(10)
    fig_rank = px.bar(df_top10, x="公司名稱", y="非擔任主管職務之全時員工薪資中位數(仟元/人)",
                      title=f"{company['產業類別']}：中位數薪資前十名公司（{latest_year}年）",
                      labels={"非擔任主管職務之全時員工薪資中位數(仟元/人)": "仟元/人"},
                      color_discrete_sequence=["#4c78a8"])
    fig_rank.update_layout(yaxis_tickformat=",", yaxis_title="仟元/人")
    charts.append(dcc.Graph(figure=fig_rank, style=hover_style))

    return company_info, charts

if __name__ == '__main__':
    app.run(debug=True)
