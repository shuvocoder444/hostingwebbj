from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HostingPackageViewSet, HostingAccountViewSet, OrderHostingView

app_name = 'hosting'

router = DefaultRouter()
router.register(r'packages', HostingPackageViewSet, basename='package')
router.register(r'accounts', HostingAccountViewSet, basename='account')

urlpatterns = [
    path('', include(router.urls)),
    path('order/', OrderHostingView.as_view(), name='order'),
]
