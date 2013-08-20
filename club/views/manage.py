from mixins import ClubManagerMixin
from django.views.generic.edit import UpdateView, CreateView
from club.models import Club, ClubLink
from club.forms import ClubCreateForm, ClubLinkForm
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from coach.mixins import JsonResponseMixin

class ClubManage(ClubManagerMixin, UpdateView):
  model = Club
  template_name = "club/manage.html"
  form_class = ClubCreateForm

  def form_valid(self, form):
    club = form.save()
    self.club = club
    return HttpResponseRedirect(reverse('club-manage', kwargs={'slug' : self.club.slug}))

  def get_context_data(self, *args, **kwargs):
    context = super(ClubManage, self).get_context_data(*args, **kwargs)
    context['stats'] = self.club.load_stats()
    context['links'] = self.club.links.all().order_by('name')
    return context

class ClubLinkAdd(ClubManagerMixin, JsonResponseMixin, CreateView):
  model = ClubLink
  template_name = "club/link/add.html"
  form_class = ClubLinkForm

  def form_valid(self, form):
    '''
    Save link on last position
    '''
    link = form.save(commit=False)
    link.club = self.club
    link.position = self.club.links.all().count() + 1
    link.save()
    return self.render_to_response(self.get_context_data(**{'form' : form}))
