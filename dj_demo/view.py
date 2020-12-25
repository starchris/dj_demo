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
    # 读csv数据
    data = pd.read_csv('data/xbot.csv').to_json(orient='records')
    # 如果是页面输入sql，直接读URL的 query，获取html上的输入
    # sql = req.query.res
    # 本地连接
    # conn = hive.Connection(host='106.75.22.252', port=10008)
    # data = pd.read_sql(sql, conn).to_json(orient='records')
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
    # 存储jsonStr
    # with open('test_decile.json') as writer:
    #     writer.write(jsonStr)

    context = {'jsonScript': jsonStr}
    return render(req, 'loop.html', context)


def condense_category(col, min_freq=0.05, new_name='other'):
    series = pd.value_counts(col)
    mask = (series / series.sum()).lt(min_freq)
    return pd.Series(np.where(col.isin(series[mask].index), new_name, col))



def t_lag(request):
    # data = pd.read_csv('data/demo.csv').to_json(orient='records')
    # server 端连接
    conn = hive.Connection(host='10.10.76.185', port=10008)
    # 本地连接
    # conn = hive.Connection(host='106.75.22.252', port=10008)
    # t1.time  from_event to_event 是变量
    # 1. 从 html 获取 3个变量的值
    values = {'start_time':"202009041600",'end_time':"202009301600",'from_event':"feed_visit",'to_event':"message_visit"}
    # 2. sql 传参为变量
    # sql = '''select
    #             date,
    #             from_event,
    #             to_event,
    #             count(s) as pv,
    #             count(distinct s) as session,
    #             count(distinct u) as user,
    #             avg(tm_diff)/1000 as avg_tm_diff,
    #             percentile_approx(tm_diff,0)/1000 as tm_diff_pct_min,
    #             percentile_approx(tm_diff,0.25)/1000 as tm_diff_pct_25,
    #             percentile_approx(tm_diff,0.5)/1000 as tm_diff_pct_50,
    #             percentile_approx(tm_diff,0.75)/1000 as tm_diff_pct_75,
    #             percentile_approx(tm_diff,1)/1000 as tm_diff_pct_max
    #         from
    #             (
    #             select
    #                 left(time,8) as date,
    #                 u, -- 用户id
    #                 s, -- session
    #                 n as from_event, --起始事件
    #                 lead(n) over (partition by u, s order by tm) as to_event, --下一个事件
    #                 tm as from_time, --起始时间
    #                 lead(tm) over (partition by u, s order by tm) as to_time, --终止时间
    #                 case
    #                     when lead(tm) over (partition by u, s order by tm) is not null then lead(tm) over (partition by uni_key, s order by tm) - tm
    #                     else 0
    #                     end as tm_diff --时间间隔（毫秒）
    #             from
    #                 gio.custom_event
    #             where
    #                 time between %(start_time)s and %(end_time)s  -- 时间段
    #             )  t1
    #         where
    #             1=1
    #             and from_event = %(from_event)s
    #             and to_event = %(to_event)s
    #         group by 1,2,3
    #         order by 1'''
    # data = pd.read_sql(sql,conn,params=values).to_json(orient='records')


    data = pd.read_sql('''
        select 
    date,
    from_event,
    to_event,
    count(s) as pv,
    count(distinct s) as session,
    count(distinct u) as user,
    avg(tm_diff)/1000 as avg_tm_diff,
    percentile_approx(tm_diff,0)/1000 as tm_diff_pct_min,
    percentile_approx(tm_diff,0.25)/1000 as tm_diff_pct_25,
    percentile_approx(tm_diff,0.5)/1000 as tm_diff_pct_50,
    percentile_approx(tm_diff,0.75)/1000 as tm_diff_pct_75,
    percentile_approx(tm_diff,1)/1000 as tm_diff_pct_max
from
    (
    select
        left(time,8) as date,
        u, -- 用户id
        s, -- session
        n as from_event, --起始事件
        lead(n) over (partition by u, s order by tm) as to_event, --下一个事件
        tm as from_time, --起始时间
        lead(tm) over (partition by u, s order by tm) as to_time, --终止时间
        case 
            when lead(tm) over (partition by u, s order by tm) is not null then lead(tm) over (partition by uni_key, s order by tm) - tm 
            else 0 
            end as tm_diff --时间间隔（毫秒）
    from 
        gio.custom_event 
    where 
        time between 202009041600 and 202009301600  -- 时间段 
    )  t1
where
    1=1
    and from_event = 'feed_visit'
    and to_event = 'message_visit'
group by 1,2,3
order by 1''', conn).to_json(orient='records')
    jsonStr = 'data=' + (data)
    context = {'jsonScript': jsonStr}
    return render(request, 't_lag.html', context)