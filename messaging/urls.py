from django.urls import path

from .views import (
    ConversationListView,
    ConversationMessagesView,
    StartConversationView,
    MarkMessagesReadView,
)


urlpatterns = [
    path(
        "",
        ConversationListView.as_view(),
        name="conversation-list",
    ),
    path(
        "start/",
        StartConversationView.as_view(),
        name="start-conversation",
    ),
    path(
        "<int:conversation_id>/",
        ConversationMessagesView.as_view(),
        name="conversation-messages",
    ),
    path(
        "<int:conversation_id>/read/",
        MarkMessagesReadView.as_view(),
        name="mark-messages-read",
    ),
]
