# coding=utf-8
from django.db import models
from django.utils.translation import ugettext_lazy as _
from users.models import Athlete
from users.notification import UserNotifications
from sport.models import Sport, SportWeek, SportDay, SportSession, SESSION_TYPES
from datetime import timedelta
from helpers import date_to_week
from django.utils import timezone
from coach.mail import MailBuilder
from plan.export import PlanPdfExporter
from interval.fields import IntervalField

class Plan(models.Model):
  name = models.CharField(max_length=250)
  creator = models.ForeignKey(Athlete, related_name='plans')

  # Dates
  start = models.DateField(null=True, blank=True) # A plan should start on monday
  created = models.DateTimeField(auto_now_add=True)
  updated = models.DateTimeField(auto_now=True)

  def __unicode__(self):
    return u'Plan: "%s" from %s' % (self.name, self.creator.username)

  def get_weeks_nb(self):
    '''
    Get current number of weeks in plan
    '''
    agg = self.sessions.aggregate(nb=models.Max('week'))
    if agg['nb'] is None:
      return 0
    return agg['nb'] + 1

  def update_weeks(self):
    '''
    Check the weeks described in sessions
    are still consecutive, starting from 0
    '''
    weeks = self.sessions.order_by('week').values_list('week', flat=True).distinct()
    for pos, week in enumerate(weeks):
      if pos != week:
        self.sessions.filter(week=week).update(week=pos)

  def calc_date(self, week, day):
    '''
    Calc the date of a day based on start date
    '''
    if not self.start:
      return None
    return self.start + timedelta(days=week*7+day)

  def publish(self, users):
    '''
    Publish a plan to specified users
    No verification on the users belonging
     to the creator here
    '''
    if not self.start:
      raise Exception("No start date on plan.")

    # Build the pdf export
    export = PlanPdfExporter(self)
    pdf = export.render()

    for u in users.all():
      # Save plan application
      pa, _ = PlanApplied.objects.get_or_create(user=u, plan=self)

      # Apply the sessions
      nb_applied = 0
      for s in self.sessions.all():
        try:
          s.apply(pa)
          nb_applied += 1
        except Exception, e:
          print 'Failed to apply plan session #%d : %s' % (s.pk, e)

      # Send an email to each user
      if nb_applied > 0:
        self.notify_athlete(u, pdf)

  def notify_athlete(self, user, pdf):
    '''
    Send an email to athlete
    with the plan attached
    '''
    # Context for html
    context = {
      'plan' : self,
      'user' : user,
    }

    # Build mail
    mb = MailBuilder('mail/plan.html', user.language)
    mb.subject = _(u'Training plan : %s') % (self.name, )
    mb.to = [user.email, ]
    mail = mb.build(context)

    # Attach Xls & send
    pdf_name = _('Training plan - %s.pdf') % self.name
    mail.attach(pdf_name, pdf, 'application/pdf')
    mail.send()

  def copy(self):
    '''
    Copy current plan & sessions
    '''

    # New plan, no start date
    data = {
      'name' : '%s - Copy' % (self.name, ),
      'creator' : self.creator,
    }
    plan = Plan.objects.create(**data)

    # Copy sessions
    for s in self.sessions.all():
      s.copy(plan)

    return plan

class PlanSession(models.Model):
  # Organisation
  plan = models.ForeignKey(Plan, related_name='sessions')
  week = models.IntegerField()
  day = models.IntegerField()

  # Dummy data, should be later specified
  # using a collections of PlanPart
  name = models.CharField(max_length=250)
  time = IntervalField(format='DHMSX', null=True, blank=True)
  distance = models.FloatField(null=True, blank=True)

  # Mappings to SportSession
  sport = models.ForeignKey(Sport)
  type = models.CharField(max_length=12, default='training', choices=SESSION_TYPES)

  # Conversation
  comments = models.OneToOneField('messages.Conversation', null=True, blank=True, related_name='plan_session')

  # Dates
  created = models.DateTimeField(auto_now_add=True)
  updated = models.DateTimeField(auto_now=True)

  @property
  def date(self):
    return self.plan.calc_date(self.week, self.day)

  def delete(self, *args, **kwargs):
    plan = self.plan # backup plan reference
    out = super(PlanSession, self).delete(*args, **kwargs) # actually delete the session
    plan.update_weeks() # Check weeks are still consecutive
    return out

  def copy(self, plan):
    '''
    Copy this session and attach it to new plan
    '''
    data = {
      'plan' : plan,
    }
    copy_fields = ('week', 'day', 'name', 'sport', 'type', )
    for f in copy_fields:
      data[f] = getattr(self, f)

    return PlanSession.objects.create(**data)

  def apply(self, application):
    '''
    Apply this plan session to a user
    '''
    if not self.date:
      raise Exception('No date to apply this session')

    # Load week
    w, year = date_to_week(self.date)
    week,_ = SportWeek.objects.get_or_create(year=year, week=w, user=application.user)

    # Load day
    day,_ = SportDay.objects.get_or_create(week=week, date=self.date)

    # Check a session does not already have this plan session
    try:
      psa = PlanSessionApplied.objects.get(plan_session=self, sport_session__day=day)
    except PlanSessionApplied.DoesNotExist:
      psa = None

    if psa:
      # retrieve sport session
      session = psa.sport_session
    else:
      # Load session
      defaults = {
          'name' : self.name,
          'distance' : self.distance,
          'time' : self.time,
      }
      session,_ = SportSession.objects.get_or_create(sport=self.sport, day=day, type=self.type, defaults=defaults)

      # Apply plan session
      PlanSessionApplied.objects.create(plan_session=self, sport_session=session, application=application)

    # Copy all comments
    if self.comments:

      # Build conversation if needed
      if not session.comments_private:
        session.build_conversation('private')

      for c in self.comments.messages.all():
        c.copy(session.comments_private)


PLAN_SESSION_APPLICATIONS = (
  ('applied', _('Applied')), # Just applied by trainer
  ('done', _('Done')), # Success
  ('failed', _('Failed')), # Failed the plan
)

class PlanApplied(models.Model):
  '''
  Links a Plan to a User
  Shows global status of a plan application
  '''
  plan = models.ForeignKey(Plan, related_name='applications')
  user = models.ForeignKey('users.Athlete', related_name='plans_applied')

  # Dates
  created = models.DateTimeField(auto_now_add=True)
  updated = models.DateTimeField(auto_now=True)

  class Meta:
    unique_together = (('user', 'plan'), )

  @property
  def status(self):
    '''
    Calc stats about sessions & theirs status
    '''
    out = {}
    for s, _name in PLAN_SESSION_APPLICATIONS:
      out[s] = self.sessions.filter(status=s).count()
    return out


class PlanSessionApplied(models.Model):
  '''
  Links a PlanSession to a SportSession
  '''
  # Links
  application = models.ForeignKey(PlanApplied, related_name='sessions')
  plan_session = models.ForeignKey(PlanSession, related_name='applications')
  sport_session = models.OneToOneField('sport.SportSession', related_name='plan_session')

  # Validation
  status = models.CharField(max_length=20, choices=PLAN_SESSION_APPLICATIONS, default='applied')
  validated = models.DateTimeField(null=True, blank=True)

  # Dates
  created = models.DateTimeField(auto_now_add=True)
  updated = models.DateTimeField(auto_now=True)
  trainer_notified = models.DateTimeField(null=True, blank=True)

  def notify_trainer(self):
    '''
    Notify trainer of new validation from user
    '''
    if self.status == 'applied':
      raise Exception('Invalid status')

    # Send UserNotification
    un = UserNotifications(self.plan_session.plan.creator)
    un.add_plan_session_applied(self)

    # Update notification date
    self.trainer_notified = timezone.now()
    self.save()
