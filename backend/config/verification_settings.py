import os

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DJANGO_SECRET_KEY'] = 'verification-only-key-not-for-serving-or-deployment-20261031'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['USE_SQL_SERVER'] = 'False'

from .settings import *

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
