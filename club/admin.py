from django.contrib import admin
from models import *

class ClubMembershipAdmin(admin.TabularInline):
  model = ClubMembership

class ClubLinkAdmin(admin.TabularInline):
  model = ClubLink

class ClubInviteAdmin(admin.ModelAdmin):
  list_display = ('recipient', 'slug', 'club', 'type', 'sender', 'created')
admin.site.register(ClubInvite, ClubInviteAdmin)

class ClubAdmin(admin.ModelAdmin):
  list_display = ('name',)
  inlines = [ClubLinkAdmin, ClubMembershipAdmin, ]
admin.site.register(Club, ClubAdmin)
