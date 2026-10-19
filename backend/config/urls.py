from django.urls import include, path
from routing.views import health

urlpatterns = [
    path("", health),
    path("api/", include("routing.urls")),
]
