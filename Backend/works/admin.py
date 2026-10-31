from django.contrib import admin

from .models import GenreMood, Production, Work


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'genres', 'moods', 'date', 'plot_source']
    list_filter = ['category', 'plot_source']
    search_fields = ['title', 'source_id']
    raw_id_fields = ['production']


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'category', 'genres', 'performance_count', 'date', 'end_date', 'popularity']
    list_filter = ['category']
    search_fields = ['code', 'title', 'key']


@admin.register(GenreMood)
class GenreMoodAdmin(admin.ModelAdmin):
    list_display = ['genres', 'moods']

