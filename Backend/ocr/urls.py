from django.urls import path

from . import views

urlpatterns = [
    path('tickets/ocr/', views.ocr_tickets, name='tickets-ocr'),
]
