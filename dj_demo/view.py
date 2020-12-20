import json

import numpy as np
from django.shortcuts import render
import pandas as pd

from pyhive import hive


def hello(request):
    data = pd.read_csv('data/demo.csv').to_json(orient='records')
    jsonStr = 'data=' + (data)
    context = {'jsonScript': jsonStr}
    return render(request, 'index.html', context)


def scatter(request):
    # data = pd.read_csv('data/demo.csv').to_json(orient='records')
    # server 端连接
    conn = hive.Connection(host='10.10.76.185', port=10008)
    # 本地连接
    # conn = hive.Connection(host='106.75.22.252', port=10008)
    data = pd.read_sql('''
        select
        t1.account_name,
        t1.company_name,
        t1.account_num,
        t1.pay_ttl,
        t1.recent,
        row_number() over(partition by t1.account_name order by t1.recent) as recency_num
    from
    (
        select
            account_name,
            company_name,
            DATEDIFF(to_date(from_utc_timestamp(current_timestamp(), 'Asia/Beijing')),pay_time) as recent,
            count(DISTINCT transaction_id) as account_num,
            sum(pay_amount) as pay_ttl
        from shixiaolu.test
        group by 1,2,3
        order by pay_ttl desc
    )t1
    having recency_num = 1
    order by pay_ttl desc
    limit 200''', conn).to_json(orient='records')
    jsonStr = 'data=' + (data)
    context = {'jsonScript': jsonStr}
    return render(request, 'scatter.html', context)


def bar(req):
    data = pd.read_csv('data/demo.csv').to_json(orient='records')
    jsonStr = 'data=' + (data)
    context = {'jsonScript': jsonStr}
    return render(req, 'scatter.html', context)


def function_scatter(req):
    data = pd.read_csv('data/dntest.csv').to_json(orient='records')
    jsonStr = 'data=' + (data)
    context = {'jsonScript': jsonStr}
    return render(req, 'function_scatter.html', context)


def word_cloud(req):
    data = pd.read_csv('data/xbot.csv').to_json(orient='records')
    jsonStr = 'originData=' + (data)
    context = {'jsonScript': jsonStr}
    return render(req, 'word_cloud.html', context)


def function_scatter2(req):
    return render(req, 'function_scatter2.html')


def loop(req):
    # server 端连接
    conn = hive.Connection(host='10.10.76.185', port=10008)
    # 本地 连接
    # conn = hive.Connection(host='106.75.22.252', port=10008)
    data = pd.read_sql('''
            select * from lppz.score_file_year_catg_20201215 where sample_ind=1 limit 200''', conn)

    decile = data['decile']
    df = data.drop(['member_no', 'percentile', 'quintile', 'decile', 'ventile', 'quarter'], axis=1)
    num_cols = df._get_numeric_data().columns
    cat_cols = df[[i for i in df.columns if i not in num_cols]]
    cat_cols = cat_cols.apply(condense_category, axis=0)
    cds = {}
    for cols in cat_cols:
        # 聚合后的数据
        ax = pd.crosstab(index=decile, columns=cat_cols[cols], normalize="index")
        cds[cols] = ax.to_json(orient='records')
        
    num_cols = df.select_dtypes(include=np.number)
    list(num_cols)
    quantile_list = [0, .2, .4, .6, .8, 1.]
    for cols in num_cols:
        try:
            num_cols[cols] = pd.qcut(num_cols[cols], q=quantile_list, duplicates='drop')
        except:
            continue
    for cols in num_cols:
        ax = pd.crosstab(index=decile, columns=num_cols[cols], normalize="index")
        cds[cols] = ax.to_json(orient='records')

    jsonStr = 'data=' + json.dumps(cds)
    context = {'jsonScript': jsonStr}
    return render(req, 'loop.html', context)


def condense_category(col, min_freq=0.05, new_name='other'):
    series = pd.value_counts(col)
    mask = (series / series.sum()).lt(min_freq)
    return pd.Series(np.where(col.isin(series[mask].index), new_name, col))
