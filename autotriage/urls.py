"""
URL configuration for autotriage project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from restapi.views import UserViewSet,GroupViewSet
from localapp.views import *

router = routers.DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)

admin.site.site_header = 'DAAS Administration'
admin.site.index_title = 'Debug and Analysis As A Service'
admin.site.site_title = 'DAAS'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('v1/', dashboard, name="dashboard"),
    path('restapi/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('trainname_by_branch/<str:branch>',trainname_by_branch, name="trainname_by_branch"),
    path('build_by_branch_train/<str:branch>/<str:train_name>',build_by_branch_train, name="build_by_branch_train"),
    path('analyze_result/', train_analyze_result , name="analyze_result"),
    path('error_basis_triage/', error_basis_triage, name="error_basis_triage"),
    path('suite_basis_triage/', suite_basis_triage, name="suite_basis_triage"),
    path('submit_optimal_solution/',submit_optimal_solution, name="submit_optimal_solution" ),
    path('submit_search_engine_error/',submit_search_engine_error, name="submit_search_engine_error" ),
    path('severe_error_triage/', severe_basis_triage, name="severe_basis_triage"),
    path('submit_severe_solution/',submit_severe_solution, name="submit_severe_solution" ),
    path('', dashboard_v2, name="dashboard_v2"),
    path('analyze_result_v2/', train_analyze_result_v2 , name="analyze_result_v2"),
    path('analyze_watchmen_url_v2/', analyze_watchmen_url_v2, name="analyze_watchmen_url_v2"),
    path('error_basis_triage_v2/', error_basis_triage_v2, name="error_basis_triage_v2"),
    path('suite_basis_triage_v2/', suite_basis_triage_v2, name="suite_basis_triage_v2"),
    path('severe_error_triage_v2/', severe_basis_triage_v2, name="severe_basis_triage_v2"),

]
# Deprecated Urls
# path('triage/<str:watchmenfolder>', faliuredata, name="faliuredata"),