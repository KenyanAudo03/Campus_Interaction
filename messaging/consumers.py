import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message
from django.contrib.auth import get_user_model
from notifications.models import Notification
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import sync_to_async
import datetime
from profiles.models import Profile 

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        self.user_group_name = f"user_{self.user.username}"

        if not await self.user_can_access_conversation(self.conversation_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)


        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        # Mark user as online
        await self.set_user_online_status(True)

        # Notify other users in the conversation
        await self.notify_user_status(True)

        await self.accept()

    async def disconnect(self, close_code):
        # Mark user as offline
        await self.set_user_online_status(False)

        # Notify other users
        await self.notify_user_status(False)

        # Leave groups
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    @database_sync_to_async
    def set_user_online_status(self, is_online):
        # Get or create profile for the user
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.is_online = is_online
        profile.last_seen = datetime.datetime.now(datetime.timezone.utc)
        profile.save(update_fields=["is_online", "last_seen"])

    async def notify_user_status(self, is_online):
        conversation = await self.get_conversation()
        for participant in await self.get_participants(conversation):
            if participant != self.user:
                # Get the online status from profile
                profile = await self.get_user_profile(participant)
                await self.channel_layer.group_send(
                    f"user_{participant.username}",
                    {
                        "type": "user_status",
                        "user": self.user.username,
                        "status": "online" if is_online else "offline",
                    },
                )

    @database_sync_to_async
    def get_user_profile(self, user):
        return Profile.objects.get_or_create(user=user)[0]
    


    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Save message and create notification
        saved_message = await self.save_message_and_create_notification(message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": self.user.username,
                "timestamp": saved_message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    @database_sync_to_async
    def get_conversation(self):
        return Conversation.objects.get(id=self.conversation_id)

    @database_sync_to_async
    def get_participants(self, conversation):
        return list(conversation.participants.all())

    @database_sync_to_async
    def user_can_access_conversation(self, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return self.user in conversation.participants.all()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message_and_create_notification(self, message):
        conversation = Conversation.objects.get(id=self.conversation_id)
        saved_message = Message.objects.create(
            conversation=conversation, sender=self.user, content=message
        )

        for recipient in conversation.participants.exclude(id=self.user.id):
            Notification.objects.create(
                recipient=recipient,
                notification_type="message",
                content_type=ContentType.objects.get_for_model(conversation),
                object_id=conversation.id,
            )

        return saved_message

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "message": event["message"],
                    "sender": event["sender"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def user_status(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "status",
                "user": event["user"],
                "status": event["status"]
            })
        )


class StatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.user_group_name = f"user_{self.user.username}"

        # Join user's personal group for status updates
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        # Mark user as online
        await self.set_user_online_status(True)

        # Notify all users who have conversations with this user
        await self.notify_status_to_contacts(True)

        await self.accept()

    async def disconnect(self, close_code):
        # Mark user as offline
        await self.set_user_online_status(False)

        # Notify contacts
        await self.notify_status_to_contacts(False)

        # Leave group
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    @database_sync_to_async
    def set_user_online_status(self, is_online):
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.is_online = is_online
        profile.last_seen = datetime.datetime.now(datetime.timezone.utc)
        profile.save(update_fields=["is_online", "last_seen"])

    @database_sync_to_async
    def get_user_contacts(self):
        # Get all users who have conversations with the current user
        contacts = list(
            User.objects.filter(conversations__participants=self.user)
            .exclude(id=self.user.id)
            .distinct()
        )
        # Get their profiles
        contact_profiles = []
        for contact in contacts:
            profile, _ = Profile.objects.get_or_create(user=contact)
            contact_profiles.append(profile)
        return contacts  # Still return users for username access

    async def notify_status_to_contacts(self, is_online):
        contacts = await self.get_user_contacts()
        for contact in contacts:
            await self.channel_layer.group_send(
                f"user_{contact.username}",
                {
                    "type": "user_status",
                    "user": self.user.username,
                    "status": "online" if is_online else "offline",
                },
            )

    async def user_status(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "status", "user": event["user"], "status": event["status"]}
            )
        )

    async def conversation_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "conversation_update",
                    "conversation_id": event["conversation_id"],
                    "last_message": event["last_message"],
                    "sender": event["sender"],
                    "timestamp": event["timestamp"],
                }
            )
        )
