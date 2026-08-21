from django.contrib import admin
from .models import Ballot, Option, Poll

admin.site.register([Poll, Option, Ballot])

# Register your models here.
