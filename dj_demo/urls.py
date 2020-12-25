from django.conf.urls import url
from django.conf import settings
from . import view
from django.views.static import serve
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    url(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    url(r'^$', view.hello),
    url('ss$', view.scatter),
    url('bar$', view.bar),
    url('function_scatter$', view.function_scatter),
    url('word_cloud$', view.word_cloud),
    url('function_scatter2$', view.function_scatter2),
    url('loop', view.loop),
    url('t_lag', view.t_lag),
]
urlpatterns += staticfiles_urlpatterns()
