from django.contrib import admin
from .models import *

class TagMappingAdmin(admin.ModelAdmin):
    model = TagMapping
    ordering = ('tag_name',)
    list_display = ['tag_name','train_name','suite_name']
    search_fields = ['tag_name','train_name','suite_name']


class SuiteTagAdmin(admin.ModelAdmin):
    model = SuiteTag
    ordering = ('name',)
    list_display = ['name']
    search_fields = ['name']

admin.site.register(TagMapping, TagMappingAdmin)
admin.site.register(SuiteTag, SuiteTagAdmin)


