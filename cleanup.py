import yaml
import os
from dash import Dash, html, dcc, Input, Output, State, ctx
from dash import dash_table
import pandas as pd
import numpy as np
import plotly.express as px
import logging
import dash
import io
import base64

logging.basicConfig(level=logging.INFO)

# Constants and file paths
CONFIG_FILE = 'config.yml'
DEFAULT_CONFIG = {
    'target': [],
    'source': {}
}

# Functions to handle the YAML configuration file
def load_or_initialize_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    else:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as file:
            yaml.safe_dump(DEFAULT_CONFIG, file, allow_unicode=True)
        return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as file:
        yaml.safe_dump(config, file, allow_unicode=True)

# Initialize configuration
config = load_or_initialize_config()

# Initialize the Dash app
app = Dash(__name__)
app.config.suppress_callback_exceptions = True

# Layout for target data configuration
app.layout = html.Div([
    html.H1("Data Cleaning Service Configuration"),
    dcc.Tabs(id="tabs", value='tab-1', children=[
        dcc.Tab(label='Configure Target', value='tab-1'),
        dcc.Tab(label='Configure Source', value='tab-2'),
        dcc.Tab(label='Data Cleaning', value='tab-3'),
    ]),
    html.Div(id='tabs-content')
])

# Callback to render content for each tab
@app.callback(
    Output('tabs-content', 'children'),
    Input('tabs', 'value')
)
def render_content(tab):
    if tab == 'tab-1':
        return html.Div(
            id='target-configuration',  # Add id to the div
            children=[
            html.H3('Target Configuration'),
            dash_table.DataTable(
                id='table-target',
                columns=[{"name": i, "id": i} for i in ["name", "type", "desc", "op", "default"]],
                data=config['target'],
                editable=True,
                row_deletable=True,
                row_selectable='single'
            ),
            html.Button('Add Row', id='adding-row-btn', n_clicks=0),
            html.Button('Save Config', id='save-config-btn', n_clicks=0),
            html.Div(id='target_save_result')  # Add hidden div
            ]
        )
    elif tab == 'tab-2':
        return html.Div(
            id='source-configuration',  # Add id to the div
            children=[
            html.H3('Source Configuration'),
            dcc.Dropdown(
                id='source-select',
                options=[{'label': k, 'value': k} for k in config['source'].keys()],
                value=None,
                placeholder='Select a source configuration'
            ),
            dash_table.DataTable(
                id='table-source',
                columns=[{"name": i, "id": i} for i in ["src", "target"]],
                data=[],
                editable=True,
                row_deletable=True,
                row_selectable='single'
            ),
            html.Div([
                html.Button('Add Source', id='adding-source-btn-source', n_clicks=0),
                dcc.Input(id='source-name-input', type='text', placeholder='Enter source name'),
            ]),
            html.Button('Add Row', id='adding-row-btn-source', n_clicks=0),
            html.Button('Save Config', id='save-config-btn-source', n_clicks=0),
            html.Div(id='source_save_result')  # Add hidden div

        ])
    else:
        return html.Div([
            html.H3('Data Cleaning'),
            dcc.Upload(
            id='upload-data',
            children=html.Button('Upload CSV File'),
            multiple=False
            ),
            dcc.Dropdown(id='csv-field-select', options=[], placeholder='Select a field to analyze'),
            dcc.Graph(id='field-graph'),
            html.Div(
            dcc.Dropdown(
                id='source-select-clean',
                options=[{'label': k, 'value': k} for k in config['source'].keys()],
                value=list(config['source'].keys())[0],
                placeholder='Select a source configuration'
            ),
            ),
            html.Button('Clean Data', id='clean-data-btn', n_clicks=0),
            dcc.Input(id='filename-input', type='text', placeholder='Enter filename to save as'),
            html.Button('Save Cleaned CSV', id='save-csv-btn', n_clicks=0)
        ])

# Define callback for adding rows to the target table
@app.callback(
    Output('table-target', 'data'),
    Input('adding-row-btn', 'n_clicks'),
    State('table-target', 'data'),
    State('table-target', 'columns'),
    prevent_initial_call=True
)
def add_row_target(n_clicks, rows, columns):
    logging.info("Adding row with n_clicks: " + str(n_clicks))
    if n_clicks > 0:
        rows.append({c['id']: '' for c in columns})
    return rows

# Define callback for saving the target configuration
@app.callback(
    Output('target_save_result', 'children'),
    Input('save-config-btn', 'n_clicks'),
    State('table-target', 'data'),
    prevent_initial_call=True
)
def save_target_config(n_clicks, data):
    logging.info("Saving config: " + str(data) + " with n_clicks: " + str(n_clicks))
    if n_clicks > 0:
        config['target'] = data
        save_config(config)
        return html.Div("Config saved successfully")

# Add callback to adding-source-btn-source
@app.callback(
    Output('source-configuration', 'children'),
    Input('adding-source-btn-source', 'n_clicks'),
    State('source-name-input', 'value'),
    prevent_initial_call=True
)
def add_source(n_clicks, source_name):
    if n_clicks > 0:
        # if source_name is None or duplicate, return the current layout
        if source_name is None or source_name in config['source']:
            return dash.no_update
        config['source'][source_name] = None
        save_config(config)
        return html.Div(
            id='source-configuration',  # Add id to the div
            children=[
            html.H3('Source Configuration'),
            dcc.Dropdown(
                id='source-select',
                options=[{'label': k, 'value': k} for k in config['source'].keys()],
                value=source_name,
                placeholder='Select a source configuration'
            ),
            dash_table.DataTable(
                id='table-source',
                columns=[{"name": i, "id": i} for i in ["src", "target"]],
                data=config['source'][source_name],
                editable=True,
                row_deletable=True,
                row_selectable='single'
            ),
            html.Div([
                html.Button('Add Source', id='adding-source-btn-source', n_clicks=0),
                dcc.Input(id='source-name-input', type='text', placeholder='Enter source name'),
            ]),
            html.Button('Add Row', id='adding-row-btn-source', n_clicks=0),
            html.Button('Save Config', id='save-config-btn-source', n_clicks=0)
            ]
        )
    
# Define callback for adding rows to the source table
@app.callback(
    Output('table-source', 'data'),
    [Input('adding-row-btn-source', 'n_clicks'), Input('source-select', 'value')],  # Add input
    State('table-source', 'data'),
    State('table-source', 'columns'),
    State('source-select', 'value'),
    prevent_initial_call=True
)
def add_row_source(n_clicks, value, rows, columns, source_name):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == 'adding-row-btn-source':
            logging.info("Adding row with n_clicks: " + str(n_clicks))
            if rows is None:
                rows = []
            rows.append({c['id']: '' for c in columns})
            return rows
        elif button_id == 'source-select':
            # read the source configuration, return the table
            logging.info("Adding row with n_clicks: "  + str(value))
            return config['source'][source_name]


# Define callback for saving the source configuration
@app.callback(
    Output('source_save_result', 'children'),
    Input('save-config-btn-source', 'n_clicks'),
    State('table-source', 'data'),
    State('source-select', 'value'),
    prevent_initial_call=True
)
def save_source_config(n_clicks, data, source_name):
    if n_clicks > 0:
        config['source'][source_name] = data
        save_config(config)
        return html.Div("Config saved successfully")


# Helper function to parse uploaded data
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        else:
            return html.Div(['Only CSV files are supported.'])
        return df
    except Exception as e:
        print(e)
        return html.Div([
            'There was an error processing this file.'
        ])

# Callback for uploading, field selection, and displaying analysis
@app.callback(
    Output('csv-field-select', 'options'),
    Output('field-graph', 'figure'),
    Input('upload-data', 'contents'),
    Input('csv-field-select', 'value'),
    State('upload-data', 'filename')
)
def update_output_and_analysis(list_of_contents, selected_field, list_of_filenames):
    ctx = dash.callback_context

    if not ctx.triggered:
        return [], {}
    else:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == 'upload-data' and list_of_contents:
            # Handle file upload
            global df
            df = parse_contents(list_of_contents, list_of_filenames)
            options = [{'label': col, 'value': col} for col in df.columns]
            return options, {}
        elif trigger_id == 'csv-field-select' and selected_field:
            # Handle field selection and display analysis
            if df is not None and selected_field in df:
                fig = px.histogram(df, x=selected_field, marginal='box',
                                   title=f"Analysis of {selected_field}")
                return dash.no_update, fig
        return [], {}


# Callback for the cleaning process and saving the cleaned data
@app.callback(
    Output('clean-data-btn', 'children'),  # This can be an output that indicates the status
    Input('clean-data-btn', 'n_clicks'),
    State('source-select-clean', 'value'),
    State('upload-data', 'contents'),
    prevent_initial_call=True
)
def clean_and_save_data(n_clicks, source, contents):
    logging.info(f"Cleaning data for source: {source} ")
    if n_clicks > 0 and contents:
        # Implement the cleaning logic here based on 'source' mappings in config
        # This would involve renaming columns, converting types, handling missing values etc.
        # Example: 
        # logging.info(f"Cleaning data for source: ${config['source'][source]['src']} to target: ${config['source'][source]['target']}")
        global df
        for field in config['source'][source]:
            src = field['src']
            target = field['target']
            df = df.rename(columns={src: target})
        # convert types follow the target configuration
        for target in config['target']:
            if target['type'] == 'int32':
                df[target['name']] = pd.to_numeric(df[target['name']], errors='coerce')
            elif target['type'] == 'float32':
                df[target['name']] = pd.to_numeric(df[target['name']], errors='coerce')
            elif target['type'] == 'str':
                df[target['name']] = df[target['name']].astype(str)
            elif target['type'] == 'bool':
                df[target['name']] = df[target['name']].astype(bool)
            elif target['type'] == 'datetime':
                df[target['name']] = pd.to_datetime(df[target['name']], errors='coerce')
            else:
                # handle other types
                pass
        
        # handle missing values
        for target in config['target']:
            # drop rows with missing values
            if target['op'] == '1':
                df = df.dropna(subset=[target['name']])
            elif target['op'] == '2':
                df[target['name']] = df[target['name']].fillna(target['default'])
            else:
                # handle other operations
                pass
        return "Data cleaned and saved successfully!"
    return "Click to clean and save data."

# Save the cleaned data to a CSV file
@app.callback(
    Output('save-csv-btn', 'children'),
    Input('save-csv-btn', 'n_clicks'),
    State('filename-input', 'value'),
    prevent_initial_call=True
)
def save_cleaned_data(n_clicks, save_filename):
    if os.path.exists(f"{save_filename}.csv"):
            return "Filename already exists. Please enter a different name."
    df.to_csv(f"{save_filename}.csv", index=False)
    return "Data cleaned and saved successfully!"



# Uncomment this line to run the app
app.run_server(debug=True)
