from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import (
    Profile, PlayerStats, Club, Court, Booking, Match, MatchParticipant,
    MatchMessage, Rating, CourtRating, Notification, CommunityPost,
    PostReply, CommunityGroup, FriendRequest, Friendship, PrivateMessage,
    BlockedUser, SavedClub
)


def get_user_avatar_url(profile, request=None):
    """Helper to get avatar URL, preferring external_avatar_url over local avatar."""
    if profile.external_avatar_url:
        return profile.external_avatar_url
    if profile.avatar:
        if request:
            return request.build_absolute_uri(profile.avatar.url)
        return profile.avatar.url
    return None


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer"""
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password', 'date_joined']
        read_only_fields = ['id', 'date_joined']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ProfileSerializer(serializers.ModelSerializer):
    """User profile serializer"""
    user = UserSerializer(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    tier_name = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'full_name', 'phone_number', 'avatar', 'avatar_url',
            'bio', 'location', 'skill_level', 'evaluation_type', 'is_verified',
            'public_skill_level', 'total_skill_ratings', 'rating_points', 'tier_level', 'tier_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'public_skill_level', 'total_skill_ratings', 'rating_points', 'tier_level', 'tier_name', 'created_at', 'updated_at']

    def get_avatar_url(self, obj):
        if obj.external_avatar_url:
            return obj.external_avatar_url
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_tier_name(self, obj):
        return obj.get_tier_name()


class PlayerStatsSerializer(serializers.ModelSerializer):
    """Player statistics serializer"""
    user = UserSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    win_rate = serializers.ReadOnlyField()
    public_skill_level = serializers.FloatField(source='user.profile.public_skill_level', read_only=True)
    total_skill_ratings = serializers.IntegerField(source='user.profile.total_skill_ratings', read_only=True)
    skill_level = serializers.IntegerField(source='user.profile.skill_level', read_only=True)

    class Meta:
        model = PlayerStats
        fields = [
            'id', 'user', 'username', 'matches_played', 'matches_won', 'matches_lost',
            'win_rate', 'total_hours', 'favorite_clubs', 'achievements',
            'skill_progression', 'badges', 'city', 'favorite_club',
            'public_skill_level', 'total_skill_ratings', 'skill_level', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'username', 'win_rate', 'public_skill_level', 'total_skill_ratings', 'skill_level', 'updated_at']


class CourtSerializer(serializers.ModelSerializer):
    """Court serializer"""
    club_name = serializers.CharField(source='club.name', read_only=True)
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = Court
        fields = [
            'id', 'club', 'club_name', 'name', 'court_type', 'is_indoor',
            'is_available', 'prices', 'price_per_hour', 'current_price',
            'features', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'club_name', 'current_price', 'created_at', 'updated_at']
        extra_kwargs = {
            'club': {'required': False}  # Club is set from URL, not from POST data
        }

    def get_current_price(self, obj):
        return obj.get_current_price()


class ClubSerializer(serializers.ModelSerializer):
    """Club serializer with nested courts"""
    courts = CourtSerializer(many=True, read_only=True)
    distance = serializers.SerializerMethodField()
    price_range = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            'id', 'name', 'address', 'city', 'postal_code', 'latitude', 'longitude',
            'phone', 'email', 'website', 'reservation_link', 'images', 'primary_photo', 'rating',
            'review_count', 'opening_hours', 'amenities', 'price_min', 'price_max',
            'currency', 'is_partner', 'courts', 'distance', 'price_range',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'review_count', 'distance', 'price_range', 'created_at', 'updated_at']

    def get_distance(self, obj):
        request = self.context.get('request')
        if request and 'lat' in request.query_params and 'lng' in request.query_params:
            return obj.get_distance_from(
                request.query_params['lat'],
                request.query_params['lng']
            )
        return None

    def get_price_range(self, obj):
        return {
            'min': float(obj.price_min),
            'max': float(obj.price_max),
            'currency': obj.currency
        }


class BookingSerializer(serializers.ModelSerializer):
    """Booking serializer"""
    court_name = serializers.CharField(source='court.name', read_only=True)
    club_name = serializers.CharField(source='court.club.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'court', 'court_name', 'club_name', 'user', 'user_name',
            'date', 'start_time', 'end_time', 'duration', 'status', 'status_display',
            'total_amount', 'currency', 'payment_intent_id', 'payment_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'court_name', 'club_name', 'user_name', 'status_display', 'created_at', 'updated_at']

    def create(self, validated_data):
        booking = super().create(validated_data)
        booking.total_amount = booking.calculate_total()
        booking.save()
        return booking


class MatchParticipantSerializer(serializers.ModelSerializer):
    """Match participant serializer"""
    user_info = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # Flutter-compatible fields at top level
    userId = serializers.IntegerField(source='user.id', read_only=True)
    userName = serializers.CharField(source='user.username', read_only=True)
    userAvatar = serializers.SerializerMethodField()
    userSkillLevel = serializers.SerializerMethodField()
    userEvaluationType = serializers.SerializerMethodField()

    class Meta:
        model = MatchParticipant
        fields = [
            'id', 'match', 'user', 'user_name', 'user_info', 'status', 'status_display',
            'amount_paid', 'payment_status', 'payment_intent_id', 'joined_at',
            'userId', 'userName', 'userAvatar', 'userSkillLevel', 'userEvaluationType'
        ]
        read_only_fields = ['id', 'user_name', 'user_info', 'status_display', 'joined_at', 'userId', 'userName', 'userAvatar', 'userSkillLevel', 'userEvaluationType']

    def get_user_info(self, obj):
        if obj.user:
            request = self.context.get('request')
            avatar_url = get_user_avatar_url(obj.user.profile, request) if hasattr(obj.user, 'profile') else None
            return {
                'id': obj.user.id,
                'username': obj.user.username,
                'skill_level': obj.user.profile.skill_level if hasattr(obj.user, 'profile') else None,
                'evaluation_type': obj.user.profile.evaluation_type if hasattr(obj.user, 'profile') else 'new',
                'avatar': avatar_url
            }
        return None

    def get_userAvatar(self, obj):
        """Get user avatar URL for Flutter"""
        if obj.user and hasattr(obj.user, 'profile'):
            request = self.context.get('request')
            return get_user_avatar_url(obj.user.profile, request)
        return None

    def get_userSkillLevel(self, obj):
        """Get user skill level for Flutter"""
        if obj.user and hasattr(obj.user, 'profile'):
            return obj.user.profile.skill_level
        return None

    def get_userEvaluationType(self, obj):
        """Get user evaluation type for Flutter"""
        if obj.user and hasattr(obj.user, 'profile'):
            return obj.user.profile.evaluation_type
        return 'new'


class MatchSerializer(serializers.ModelSerializer):
    """Match serializer"""
    participants = MatchParticipantSerializer(many=True, read_only=True)
    organizer_info = serializers.SerializerMethodField()
    organizer_name = serializers.CharField(source='organizer.username', read_only=True)
    location = serializers.SerializerMethodField()
    club_name = serializers.CharField(source='club.name', read_only=True)
    court_name = serializers.CharField(source='court.name', read_only=True)
    participants_count = serializers.SerializerMethodField()
    share_link = serializers.SerializerMethodField()

    # Backward compatibility fields for booking-based matches
    date = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'title', 'description', 'match_type', 'club', 'club_name',
            'court', 'court_name', 'booking', 'date_time', 'duration',
            'date', 'start_time', 'end_time',  # Backward compatibility
            'organizer', 'organizer_name', 'organizer_info', 'max_players',
            'min_skill_level', 'max_skill_level', 'price_per_player', 'currency',
            'evaluation_type', 'min_skill_level_new', 'max_skill_level_new',
            'min_skill_level_old', 'max_skill_level_old',
            'status', 'is_public', 'is_open', 'share_code', 'share_link',
            'participants', 'participants_count', 'location', 'winners', 'losers',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organizer', 'organizer_name', 'organizer_info', 'club_name', 'court_name',
            'participants_count', 'location', 'share_code', 'share_link',
            'date', 'start_time', 'end_time', 'created_at', 'updated_at'
        ]

    def get_organizer_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.organizer.profile, request) if hasattr(obj.organizer, 'profile') else None
        return {
            'id': obj.organizer.id,
            'username': obj.organizer.username,
            'skill_level': obj.organizer.profile.skill_level if hasattr(obj.organizer, 'profile') else None,
            'evaluation_type': obj.organizer.profile.evaluation_type if hasattr(obj.organizer, 'profile') else 'new',
            'avatar': avatar_url
        }

    def get_location(self, obj):
        return obj.get_location_info()

    def get_participants_count(self, obj):
        return obj.get_accepted_participants_count()

    def get_share_link(self, obj):
        if obj.share_code:
            return f'/match/share/{obj.share_code}'
        return None

    def get_date(self, obj):
        if obj.booking:
            return obj.booking.date
        return obj.date_time.date()

    def get_start_time(self, obj):
        if obj.booking:
            return obj.booking.start_time
        return obj.date_time.time()

    def get_end_time(self, obj):
        if obj.booking:
            return obj.booking.end_time
        from datetime import timedelta
        end_time = obj.date_time + timedelta(minutes=obj.duration)
        return end_time.time()

    def create(self, validated_data):
        match = super().create(validated_data)
        # Automatically add organizer as confirmed participant
        MatchParticipant.objects.create(
            match=match,
            user=match.organizer,
            status='confirmed'
        )
        return match


class MatchMessageSerializer(serializers.ModelSerializer):
    """Match chat message serializer"""
    sender_info = serializers.SerializerMethodField()
    sender_name = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = MatchMessage
        fields = ['id', 'match', 'sender', 'sender_name', 'sender_info', 'content', 'created_at']
        read_only_fields = ['id', 'sender_name', 'sender_info', 'created_at']

    def get_sender_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.sender.profile, request) if hasattr(obj.sender, 'profile') else None
        return {
            'id': obj.sender.id,
            'username': obj.sender.username,
            'avatar': avatar_url
        }


class RatingSerializer(serializers.ModelSerializer):
    """Player rating serializer"""
    rater_name = serializers.CharField(source='rater.username', read_only=True)
    rated_user_name = serializers.CharField(source='rated_user.username', read_only=True)

    class Meta:
        model = Rating
        fields = [
            'id', 'match', 'rater', 'rater_name', 'rated_user',
            'rated_user_name', 'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'rater', 'rater_name', 'rated_user_name', 'created_at']


class CourtRatingSerializer(serializers.ModelSerializer):
    """Court rating serializer"""
    rater_name = serializers.CharField(source='rater.username', read_only=True)
    court_name = serializers.CharField(source='court.name', read_only=True)
    club_name = serializers.CharField(source='court.club.name', read_only=True)

    class Meta:
        model = CourtRating
        fields = [
            'id', 'court', 'court_name', 'club_name', 'match', 'rater',
            'rater_name', 'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'court_name', 'club_name', 'rater_name', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Notification serializer"""
    match_info = serializers.SerializerMethodField()
    friend_request_info = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'type', 'type_display', 'match', 'match_info',
            'friend_request', 'friend_request_info', 'message', 'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'type_display', 'match_info', 'friend_request_info', 'created_at']

    def get_match_info(self, obj):
        if obj.match:
            return {
                'id': obj.match.id,
                'title': obj.match.title,
                'date_time': obj.match.date_time
            }
        return None

    def get_friend_request_info(self, obj):
        if obj.friend_request:
            return {
                'id': obj.friend_request.id,
                'sender_id': obj.friend_request.sender.id,
                'sender_username': obj.friend_request.sender.username,
                'receiver_id': obj.friend_request.receiver.id,
                'receiver_username': obj.friend_request.receiver.username,
                'status': obj.friend_request.status
            }
        return None


class PostReplySerializer(serializers.ModelSerializer):
    """Post reply serializer with nested replies"""
    author_info = serializers.SerializerMethodField()
    author_name = serializers.CharField(source='author.username', read_only=True)
    author_avatar = serializers.SerializerMethodField()
    child_replies = serializers.SerializerMethodField()
    like_count = serializers.ReadOnlyField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = PostReply
        fields = [
            'id', 'post', 'author', 'author_name', 'author_info', 'author_avatar',
            'content', 'parent_reply', 'child_replies', 'likes', 'like_count',
            'is_liked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author_name', 'author_info', 'author_avatar', 'child_replies', 'like_count', 'is_liked', 'created_at', 'updated_at']

    def get_author_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.author.profile, request) if hasattr(obj.author, 'profile') else None
        return {
            'id': obj.author.id,
            'username': obj.author.username,
            'avatar': avatar_url
        }

    def get_author_avatar(self, obj):
        try:
            request = self.context.get('request')
            return get_user_avatar_url(obj.author.profile, request)
        except:
            return None

    def get_child_replies(self, obj):
        if obj.parent_reply is None:
            children = obj.child_replies.all()
            return PostReplySerializer(children, many=True, context=self.context).data
        return []

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


class CommunityPostSerializer(serializers.ModelSerializer):
    """Community post serializer"""
    author_info = serializers.SerializerMethodField()
    author_name = serializers.CharField(source='author.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    replies = PostReplySerializer(many=True, read_only=True)
    like_count = serializers.ReadOnlyField()
    reply_count = serializers.ReadOnlyField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = CommunityPost
        fields = [
            'id', 'author', 'author_name', 'author_info', 'title', 'content',
            'category', 'category_display', 'city', 'group', 'group_name',
            'likes', 'like_count', 'reply_count', 'is_liked', 'replies',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author_name', 'author_info', 'category_display', 'group_name', 'like_count', 'reply_count', 'is_liked', 'created_at', 'updated_at']

    def get_author_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.author.profile, request) if hasattr(obj.author, 'profile') else None
        return {
            'id': obj.author.id,
            'username': obj.author.username,
            'avatar': avatar_url
        }

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


class CommunityGroupSerializer(serializers.ModelSerializer):
    """Community group serializer"""
    creator_info = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    club_name = serializers.CharField(source='club.name', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = CommunityGroup
        fields = [
            'id', 'name', 'description', 'theme', 'city', 'club', 'club_name',
            'creator', 'creator_name', 'creator_info', 'members', 'member_count',
            'is_public', 'created_at'
        ]
        read_only_fields = ['id', 'creator_name', 'creator_info', 'club_name', 'member_count', 'created_at']

    def get_creator_info(self, obj):
        return {
            'id': obj.creator.id,
            'username': obj.creator.username
        }

    def get_member_count(self, obj):
        return obj.members.count()


class FriendRequestSerializer(serializers.ModelSerializer):
    """Friend request serializer"""
    sender_info = serializers.SerializerMethodField()
    receiver_info = serializers.SerializerMethodField()
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    receiver_name = serializers.CharField(source='receiver.username', read_only=True)
    sender_profile = serializers.SerializerMethodField()
    receiver_profile = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = [
            'id', 'sender', 'sender_name', 'sender_info', 'sender_profile',
            'receiver', 'receiver_name', 'receiver_info', 'receiver_profile',
            'status', 'message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'sender_name', 'sender_info', 'sender_profile', 'receiver_name', 'receiver_info', 'receiver_profile', 'created_at', 'updated_at']

    def get_sender_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.sender.profile, request) if hasattr(obj.sender, 'profile') else None
        return {
            'id': obj.sender.id,
            'username': obj.sender.username,
            'avatar': avatar_url
        }

    def get_receiver_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.receiver.profile, request) if hasattr(obj.receiver, 'profile') else None
        return {
            'id': obj.receiver.id,
            'username': obj.receiver.username,
            'avatar': avatar_url
        }

    def get_sender_profile(self, obj):
        try:
            profile = obj.sender.profile
            request = self.context.get('request')
            return {
                'skill_level': profile.skill_level,
                'evaluation_type': profile.evaluation_type,
                'avatar': get_user_avatar_url(profile, request)
            }
        except:
            return None

    def get_receiver_profile(self, obj):
        try:
            profile = obj.receiver.profile
            request = self.context.get('request')
            return {
                'skill_level': profile.skill_level,
                'evaluation_type': profile.evaluation_type,
                'avatar': get_user_avatar_url(profile, request)
            }
        except:
            return None


class FriendshipSerializer(serializers.ModelSerializer):
    """Friendship serializer"""
    friend = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ['id', 'user1', 'user2', 'friend', 'created_at']
        read_only_fields = ['id', 'friend', 'created_at']

    def get_friend(self, obj):
        request = self.context.get('request')
        if request and request.user:
            friend = obj.user2 if obj.user1 == request.user else obj.user1
            avatar_url = get_user_avatar_url(friend.profile, request) if hasattr(friend, 'profile') else None
            return {
                'id': friend.id,
                'username': friend.username,
                'email': friend.email,
                'skill_level': friend.profile.skill_level if hasattr(friend, 'profile') else None,
                'evaluation_type': friend.profile.evaluation_type if hasattr(friend, 'profile') else 'new',
                'avatar': avatar_url
            }
        return None


class PrivateMessageSerializer(serializers.ModelSerializer):
    """Private message serializer"""
    sender_info = serializers.SerializerMethodField()
    receiver_info = serializers.SerializerMethodField()
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    receiver_name = serializers.CharField(source='receiver.username', read_only=True)

    class Meta:
        model = PrivateMessage
        fields = [
            'id', 'sender', 'sender_name', 'sender_info', 'receiver',
            'receiver_name', 'receiver_info', 'content', 'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'sender_name', 'sender_info', 'receiver_name', 'receiver_info', 'created_at']

    def get_sender_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.sender.profile, request) if hasattr(obj.sender, 'profile') else None
        return {
            'id': obj.sender.id,
            'username': obj.sender.username,
            'avatar': avatar_url
        }

    def get_receiver_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.receiver.profile, request) if hasattr(obj.receiver, 'profile') else None
        return {
            'id': obj.receiver.id,
            'username': obj.receiver.username,
            'avatar': avatar_url
        }


class BlockedUserSerializer(serializers.ModelSerializer):
    """Blocked user serializer"""
    blocker_info = serializers.SerializerMethodField()
    blocked_info = serializers.SerializerMethodField()

    class Meta:
        model = BlockedUser
        fields = [
            'id', 'blocker', 'blocker_info', 'blocked', 'blocked_info',
            'reason', 'created_at'
        ]
        read_only_fields = ['id', 'blocker_info', 'blocked_info', 'created_at']

    def get_blocker_info(self, obj):
        return {
            'id': obj.blocker.id,
            'username': obj.blocker.username
        }

    def get_blocked_info(self, obj):
        request = self.context.get('request')
        avatar_url = get_user_avatar_url(obj.blocked.profile, request) if hasattr(obj.blocked, 'profile') else None
        return {
            'id': obj.blocked.id,
            'username': obj.blocked.username,
            'avatar': avatar_url
        }


class SavedClubSerializer(serializers.ModelSerializer):
    """Saved/favorite club serializer"""
    club_details = ClubSerializer(source='club', read_only=True)

    class Meta:
        model = SavedClub
        fields = ['id', 'user', 'club', 'club_details', 'created_at']
        read_only_fields = ['id', 'user', 'club_details', 'created_at']


# Authentication Serializers
class RegisterSerializer(serializers.ModelSerializer):
    """Registration serializer"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)
    full_name = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ['username', 'password', 'password2', 'email', 'first_name', 'last_name', 'full_name']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "User with this email already exists."})

        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        full_name = validated_data.pop('full_name', '')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )

        # Update profile with full name
        if full_name and hasattr(user, 'profile'):
            user.profile.full_name = full_name
            user.profile.save()

        return user


class LoginSerializer(serializers.Serializer):
    """Login serializer"""
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        username = attrs.get('username')
        password = attrs.get('password')

        if not email and not username:
            raise serializers.ValidationError("Either email or username must be provided.")

        return attrs


class ProfileSetupSerializer(serializers.ModelSerializer):
    """Profile setup after registration"""
    class Meta:
        model = Profile
        fields = ['avatar', 'location', 'bio', 'skill_level', 'evaluation_type']


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Profile update serializer"""
    user_first_name = serializers.CharField(source='user.first_name', required=False)
    user_last_name = serializers.CharField(source='user.last_name', required=False)
    user_email = serializers.EmailField(source='user.email', required=False)

    class Meta:
        model = Profile
        fields = [
            'phone_number', 'full_name', 'avatar', 'external_avatar_url', 'bio', 'location',
            'skill_level', 'evaluation_type', 'user_first_name', 'user_last_name', 'user_email'
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})

        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


# Nested serializers for detailed responses
class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user serializer with profile and stats"""
    profile = ProfileSerializer(read_only=True)
    stats = PlayerStatsSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'profile', 'stats']
        read_only_fields = ['id', 'date_joined']


class MatchDetailSerializer(MatchSerializer):
    """Detailed match serializer with all relations"""
    messages = MatchMessageSerializer(many=True, read_only=True)
    court_ratings = CourtRatingSerializer(many=True, read_only=True)

    class Meta(MatchSerializer.Meta):
        fields = MatchSerializer.Meta.fields + ['messages', 'court_ratings']