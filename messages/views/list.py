from django.views.generic import ListView, DetailView
from coach.mixins import JsonResponseMixin
from mixins import MessageSessionMixin, ConversationMixin

class ConversationView(ConversationMixin, DetailView):
  template_name = 'messages/conversation.html'

  def get_object(self):
    return self.get_conversation()

class ConversationList(JsonResponseMixin, ConversationMixin, ListView):
  template_name = 'messages/_list.html'
  context_object_name = 'messages'
  list_type = None

  max_page = 6 # At first, only show 6 messages
  full = True

  def get_context_data(self):
    context = super(ConversationList, self).get_context_data()

    # Current main conversation
    context['conversation'] = self.conversation
    context['session'] = self.session
    context['privacy'] = self.privacy

    # List all available conversations for user
    conversations = []
    if 'comments_private' in self.privacy and self.session.comments_private:
      conversations.append(self.session.comments_private)
    if 'comments_public' in self.privacy and self.session.comments_public:
      conversations.append(self.session.comments_public)
    context['conversations'] = conversations

    # Pagination
    context['full'] = self.full
    if not self.full:
      context['remaining'] = self.total - self.max_page

    return context

  def get_queryset(self):
    # Load conversation
    self.get_conversation()

    # List all messages by creation date
    messages = self.conversation.messages.order_by('created')
    self.total = messages.count() # all messages in conversation

    # By default, limit to nb_page (non full mode)
    # Listing last comments
    if self.total > self.max_page and not self.kwargs['full']:
      self.full = False
      messages = messages[self.total-self.max_page:]

    return messages
