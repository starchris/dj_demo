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
    conn = hive.Connection(host='10.10.76.185', port=10008)
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