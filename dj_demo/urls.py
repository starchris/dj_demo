from django.conf.urls import url
from django.urls import path, include
from django.conf import settings
from . import view
from django.views.static import serve
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    url(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    url(r'^$', view.hello),
    url('^ss$', view.scatter),
    url('^bar$', view.bar),
    url('^function_scatter$', view.function_scatter),
    url('^word_cloud$', view.word_cloud),
    url('^function_scatter2$', view.function_scatter2),
    url('^loop$', view.loop),
    url('^loop_tables/(?P<table_name>.*)$', view.loop_tables),
    url('^loop_tables_carbon/(?P<table_name>.*)$', view.loop_tables_carbon),
    url('^loop_tables_clickhouse/(?P<table_name>.*)$', view.loop_tables_clickhouse),
    url('^t_lag$', view.t_lag),
    url('^loop_feature/(?P<table_name>.*)$', view.loop_feature),

    # 企业经营洞察与招聘预算分析 Agent - 飞书机器人接口
    path('', include('biz_intel_agent.urls')),
]
urlpatterns += staticfiles_urlpatterns()
