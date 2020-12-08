from django.conf.urls import url
from . import view

urlpatterns = [
    url(r'^$', view.hello),
    url('ss', view.scatter),
    url('bar', view.bar),
    url('function_scatter', view.function_scatter),
]
