#!/bin/bash -ex
python manage.py runserver 0.0.0.0:80 &
disown
