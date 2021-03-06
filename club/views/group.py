from .mixins import ClubGroupMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from coach.mixins import JsonResponseMixin


class ClubGroupList(ClubGroupMixin, ListView):
  public = True
  context_object_name = 'groups'
  template_name = 'club/group/index.html'

class ClubGroupCreate(ClubGroupMixin, CreateView):
  template_name = 'club/group/edit.html'

class ClubGroupEdit(ClubGroupMixin, UpdateView):
  template_name = 'club/group/edit.html'

class ClubGroupView(ClubGroupMixin, DetailView):
  public = True
  template_name = 'club/group/view.html'

class ClubGroupMembers(ClubGroupMixin, JsonResponseMixin, ListView):
  template_name = 'club/group/members.html'

  def post(self, *args, **kwargs):
    self.object_list = self.get_queryset()
    self.get_object() # load objects

    # Add member
    action = self.request.POST['action']
    member = self.club.clubmembership_set.get(trainers=self.request.user, pk=self.request.POST['member'])
    if action == 'add':
      self.group.members.add(member)
    elif action == 'remove':
      self.group.members.remove(member)

    return self.render_to_response(self.get_context_data())

  def get_context_data(self, *args, **kwargs):
    context = super(ClubGroupMembers, self).get_context_data(*args, **kwargs)

    # Load all memberships in club with
    # current user as trainer
    memberships = self.club.clubmembership_set.filter(trainers=self.request.user).prefetch_related('user')
    memberships = memberships.exclude(role__in=('prospect', 'archive'))
    memberships = memberships.order_by('user__first_name', 'user__last_name')
    context['memberships'] = memberships

    # Get active memberships pk
    context['group_members'] = memberships.filter(groups=self.group).values_list('pk', flat=True)

    return context

