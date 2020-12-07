import json
from django.shortcuts import render
import pandas as pd


def hello(request):
    data = pd.read_sql('''
    ''').to_json(orient='records')
    jsonStr = 'data='+(data)
    context = {'jsonScript': jsonStr}
    return render(request, 'index.html', context)

def scatter(request):
    data = pd.read_csv('data/demo.csv').to_json(orient='records')
    jsonStr = 'data='+(data)
    context = {'jsonScript': jsonStr}
    return render(request, 'scatter.html', context)


def bar(req):
    data = pd.read_csv('data/demo.csv').to_json(orient='records')
    jsonStr = 'data='+(data)
    context = {'jsonScript': jsonStr}
    return render(req, 'scatter.html', context)
