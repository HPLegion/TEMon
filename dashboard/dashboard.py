import datetime
from logging.config import dictConfig

import pytz
import redis

from dash import Dash
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html

#### Constants and stuff ####
TZ = pytz.timezone('Europe/Zurich')
_BUFFERLEN = 7200
_BOOTSTRAP_CDN = "https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css"
PSUS = ["HV_GunBias", "HV_AnodeDt", "HV_InnerBarrier", "HV_Extractor", "GUN_CathodeHeating",
        "GUN_Wehnelt", "GUN_Anode", "GUN_Suppressor", "GUN_Collector", "GUN_Extractor"]
GAUGES = ["EBIS_Gun_Penning", "EBIS_Collector_Penning"]

#### Initialisation ####
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': "[%(asctime)s][%(levelname)s]:%(message)s",
    }},
    'root': {
        'level': 'INFO',
    }
})
app = Dash(__name__, external_stylesheets=[_BOOTSTRAP_CDN])
server = app.server # expose in case we are running with gunicorn
logger = server.logger
logger.info("Dash initialised")

rcl = redis.Redis(host='redis')
logger.info("Redis connection opened.")


#### Page Content ####
_HEADER = html.Section(className="text-center", children=[
    html.H1("TwinEBIS monitoring", className="mb-3"),
    html.Hr()
])

_FOOTER = html.Section(className="text-justify", children=[
    html.Hr()
])

_BODY = html.Div(className="container", children=[
    html.Label("History (min)", htmlFor="ctrl_time"),
    dcc.Input(id="ctrl_time", type="number", className="form-control",
              value=5, min=1, max=120, debounce=True),
    dcc.RadioItems(
        id="ctrl_category",
        options=[
            {'label': 'Currents', 'value': 'Currents'},
            {'label': 'Pressures', 'value': 'Pressures'},
            ],
        value='Currents',
        labelStyle={'display': 'inline-block'}
    ),
    dcc.Graph(id='plot', style={"height":700}),
    dcc.Interval(
        id='interval_update',
        interval=1000, # in milliseconds
        n_intervals=0
    )
])

app.layout = html.Div(className="container-fluid", children=[_HEADER, _BODY, _FOOTER])


#### Callback Definition ####
@app.callback(
    Output("plot", 'figure'),
    [Input('interval_update', 'n_intervals'),
     Input("ctrl_time", "value"),
     Input("ctrl_category", "value")]
)
def update_plot(_, mins, category):
    """This function creates the plot"""
    data = []
    if category == "Currents":
        for psu in PSUS:
            with rcl.pipeline(transaction=True) as pipe:
                pipe.lrange(f"psu:{psu}:iread:val", 0, _BUFFERLEN-1)
                pipe.lrange(f"psu:{psu}:iread:t", 0, _BUFFERLEN-1)
                responses = pipe.execute()
            vals = list(map(float, [x.decode("utf-8") for x in responses[0]]))
            ts = list(map(datetime.datetime.fromisoformat, [x.decode("utf-8") for x in responses[1]]))
            logger.info(f"Pulled from psu:{psu}:iread")

            data.append({"x": ts, "y":vals, "name":psu, "type":"line"})
        yaxis = {"title":"Current (A)"}
    elif category == "Pressures":
        for gauge in GAUGES:
            with rcl.pipeline(transaction=True) as pipe:
                pipe.lrange(f"gauge:{gauge}:val", 0, _BUFFERLEN-1)
                pipe.lrange(f"gauge:{gauge}:t", 0, _BUFFERLEN-1)
                responses = pipe.execute()
            vals = list(map(float, [x.decode("utf-8") for x in responses[0]]))
            ts = list(map(datetime.datetime.fromisoformat, [x.decode("utf-8") for x in responses[1]]))
            logger.info(f"Pulled from gauge:{gauge}")

            data.append({"x": ts, "y":vals, "name":gauge, "type":"line"})
        yaxis = {"title":"Pressure (mbar)", "tickformat":".2e", "type":"log"}

    highlim = datetime.datetime.now(TZ)
    lowlim = highlim - datetime.timedelta(minutes=mins)
    layout = {
        "title":category,
        "template":"plotly_dark",
        "xaxis":{"range":[lowlim, highlim]},
        "yaxis":yaxis,
        "uirevision":1
    }

    return {"data":data, "layout":layout}


if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0")
