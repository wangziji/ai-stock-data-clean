import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
import pandas as pd
import io
import base64
import plotly.graph_objects as go

app = dash.Dash("Stock Viewer")
app.config.suppress_callback_exceptions = True

app.layout = html.Div([
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        multiple=False
    ),
    html.Div(id='output-data-upload'),
])

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            return df
    except Exception as e:
        print(e)

@app.callback(Output('output-data-upload', 'children'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'))
def update_output(contents, filename):
    if contents:
        global df
        df = parse_contents(contents, filename)
        names = df['n'].unique()
        return html.Div([
            html.H5(filename),
            html.Hr(),
            dcc.Dropdown(
                id='name-dropdown',
                options=[{'label': name, 'value': name} for name in names],
                value=names[0],
                style={'width': '30%'}
            ),
            dcc.Graph(id='k-line-graph', style={'height': '900px'}),
            # 这里可以添加你的代码来处理数据
        ])
    
@app.callback(
    Output('k-line-graph', 'figure'),
    [Input('name-dropdown', 'value')]
)
def update_graph(selected_name):
    df_stock = df[df['n'] == selected_name]
    fig = go.Figure(data=[go.Candlestick(
        x=df_stock['d'],
        open=df_stock['o'],
        high=df_stock['h'],
        low=df_stock['l'],
        close=df_stock['c']
    )])
    fig.update_layout(title=selected_name + ' Stock', xaxis_rangeslider_visible=False)
    return fig

if __name__ == '__main__':
    app.run_server(debug=True, port=8051)