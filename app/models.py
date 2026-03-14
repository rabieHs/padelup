from django.contrib.auth.models import User
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import os
import random
import string
from datetime import datetime
from django.utils import timezone
import pytz


def avatar_upload_path(instance, filename):
    return f'avatars/{instance.user.username}/{filename}'


def club_photo_upload_path(instance, filename):
    return f'clubs/{instance.name}/{filename}'


class Profile(models.Model):
    """Extended user profile matching Flutter UserModel"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    external_avatar_url = models.URLField(max_length=500, blank=True, default='')
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=255, blank=True)
    skill_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        default=5
    )
    EVALUATION_TYPE_CHOICES = [
        ('new', 'New (1-8)'),
        ('old', 'Old (1-10)'),
    ]
    evaluation_type = models.CharField(max_length=10, choices=EVALUATION_TYPE_CHOICES, default='new')
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Rating system
    public_skill_level = models.FloatField(null=True, blank=True)
    total_skill_ratings = models.IntegerField(default=0)
    rating_points = models.IntegerField(default=0)  # Sum of all ratings received
    tier_level = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])  # 1-10 tier based on avg rating

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_tier_name(self):
        """Get tier name based on tier_level"""
        tier_names = {
            1: "Découverte",
            2: "Initiation",
            3: "Loisir",
            4: "Partenaire",
            5: "Adversaire",
            6: "Stratège",
            7: "Perfectionniste",
            8: "Challenger",
            9: "Compétiteur",
            10: "Élite"
        }
        return tier_names.get(self.tier_level, "Découverte")

    def update_public_rating(self):
        """Calculate and update the public rating based on received ratings"""
        from django.db.models import Avg, Sum
        ratings = Rating.objects.filter(rated_user=self.user)

        avg_rating = ratings.aggregate(avg=Avg('rating'))['avg']
        sum_ratings = ratings.aggregate(sum=Sum('rating'))['sum']

        if avg_rating is not None:
            self.public_skill_level = round(avg_rating, 1)
            self.total_skill_ratings = ratings.count()
            self.rating_points = sum_ratings if sum_ratings else 0
            # Tier level is based on average rating (1-10 scale)
            # Round the average to nearest integer for tier
            self.tier_level = min(10, max(1, round(avg_rating)))
            self.save()


class PlayerStats(models.Model):
    """User statistics matching Flutter UserStats"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stats')
    matches_played = models.IntegerField(default=0)
    matches_won = models.IntegerField(default=0)
    matches_lost = models.IntegerField(default=0)
    total_hours = models.FloatField(default=0.0)  # Changed to FloatField to store decimal hours
    favorite_clubs = models.IntegerField(default=0)
    achievements = models.JSONField(default=list)
    skill_progression = models.JSONField(default=list)
    badges = models.JSONField(default=list)
    city = models.CharField(max_length=100, blank=True)
    favorite_club = models.ForeignKey('Club', on_delete=models.SET_NULL, null=True, blank=True, related_name='regular_players')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} stats"

    @property
    def win_rate(self):
        if self.matches_played == 0:
            return 0.0
        return round((self.matches_won / self.matches_played) * 100, 1)

    def add_skill_progression_entry(self, skill_level, date=None):
        entry = {
            'skill_level': skill_level,
            'date': (date or datetime.now()).isoformat()
        }
        if not self.skill_progression:
            self.skill_progression = []
        self.skill_progression.append(entry)
        self.save()


class Club(models.Model):
    """Club model matching Flutter ClubModel"""
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)  # -90.123456 to 90.123456
    longitude = models.DecimalField(max_digits=10, decimal_places=6)  # -180.123456 to 180.123456

    # Contact info
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    website = models.URLField(blank=True, null=True)
    reservation_link = models.URLField(blank=True, null=True)  # External booking/reservation link

    # Images - multiple images support
    images = models.JSONField(default=list, blank=True)  # List of image URLs
    primary_photo = models.ImageField(upload_to=club_photo_upload_path, blank=True, null=True)

    # Ratings
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    review_count = models.IntegerField(default=0)

    # Opening hours - stored as JSON for flexibility
    opening_hours = models.JSONField(default=dict)  # {"monday": "08:00-22:00", "tuesday": "08:00-22:00", ...}

    # Features and amenities
    amenities = models.JSONField(default=list)  # ["Parking", "Lockers", "Shower", "Pro Shop", etc.]

    # Price range
    price_min = models.DecimalField(max_digits=6, decimal_places=2, default=25.00)
    price_max = models.DecimalField(max_digits=6, decimal_places=2, default=60.00)
    currency = models.CharField(max_length=3, default='EUR')

    # Partnership status
    is_partner = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def update_rating(self):
        """Update club rating based on court ratings"""
        from django.db.models import Avg
        avg_rating = CourtRating.objects.filter(
            court__club=self
        ).aggregate(avg=Avg('rating'))['avg']

        if avg_rating is not None:
            self.rating = round(avg_rating, 1)
            self.review_count = CourtRating.objects.filter(court__club=self).count()
            self.save()

    def get_distance_from(self, lat, lng):
        """Calculate distance from given coordinates (simplified)"""
        # Simplified distance calculation - in production use proper geospatial libraries
        import math
        lat1, lon1 = float(self.latitude), float(self.longitude)
        lat2, lon2 = float(lat), float(lng)

        R = 6371  # Earth's radius in km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat/2) * math.sin(dLat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        return round(distance, 1)


class Court(models.Model):
    """Court model matching Flutter CourtModel"""
    COURT_TYPES = [
        ('glass', 'Glass Court'),
        ('indoor', 'Indoor Court'),
        ('outdoor', 'Outdoor Court'),
        ('concrete', 'Concrete Court'),
        ('premium', 'Premium Court'),
        ('standard', 'Standard Court'),
    ]

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='courts')
    name = models.CharField(max_length=100)
    court_type = models.CharField(max_length=20, choices=COURT_TYPES, default='standard')
    is_indoor = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)

    # Pricing - support for peak/off-peak
    prices = models.JSONField(default=dict)  # {"peak": 45.00, "off_peak": 30.00, "weekend": 50.00}
    price_per_hour = models.DecimalField(max_digits=6, decimal_places=2, default=35.00)  # Default/standard price

    # Features
    features = models.JSONField(default=list)  # ["LED Lighting", "Climate Control", "Premium Surface", etc.]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.club.name}"

    def get_current_price(self):
        """Get current price based on time of day"""
        now = timezone.now()
        hour = now.hour

        if self.prices:
            # Peak hours (18:00-21:00)
            if 18 <= hour < 21:
                return self.prices.get('peak', self.price_per_hour)
            # Weekend
            elif now.weekday() >= 5:
                return self.prices.get('weekend', self.price_per_hour)
            # Off-peak
            else:
                return self.prices.get('off_peak', self.price_per_hour)

        return self.price_per_hour


class Booking(models.Model):
    """Booking model for court reservations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration = models.IntegerField(default=60)  # Duration in minutes

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Payment info
    total_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='EUR')
    payment_intent_id = models.CharField(max_length=200, blank=True)
    payment_status = models.CharField(max_length=20, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']
        unique_together = ['court', 'date', 'start_time']

    def __str__(self):
        return f"{self.court.name} - {self.date} {self.start_time}"

    def calculate_total(self):
        """Calculate total amount based on duration and court price"""
        hours = self.duration / 60
        self.total_amount = float(self.court.get_current_price()) * hours
        return self.total_amount


class Match(models.Model):
    """Match model matching Flutter MatchModel"""
    MATCH_TYPES = [
        ('casual', 'Casual'),
        ('competitive', 'Competitive'),
        ('tournament', 'Tournament'),
        ('training', 'Training'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('full', 'Full'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Basic info
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, max_length=200)
    match_type = models.CharField(max_length=20, choices=MATCH_TYPES, default='casual')

    # Location and timing
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='matches')
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='matches')
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='match', null=True, blank=True)

    date_time = models.DateTimeField()
    duration = models.IntegerField(default=60)  # Duration in minutes

    # Organizer
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_matches')

    # Player settings
    max_players = models.IntegerField(default=4, validators=[MinValueValidator(2), MaxValueValidator(4)])
    min_skill_level = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])
    max_skill_level = models.IntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)])

    # Dual evaluation grille support
    EVALUATION_TYPE_CHOICES = [
        ('new', 'New (1-8)'),
        ('old', 'Old (1-10)'),
    ]
    evaluation_type = models.CharField(max_length=10, choices=EVALUATION_TYPE_CHOICES, default='new')
    min_skill_level_new = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(8)])
    max_skill_level_new = models.IntegerField(default=8, validators=[MinValueValidator(1), MaxValueValidator(8)])
    min_skill_level_old = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])
    max_skill_level_old = models.IntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)])

    # Pricing
    price_per_player = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='EUR')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    is_public = models.BooleanField(default=True)
    is_open = models.BooleanField(default=True)

    # Share code for private matches
    share_code = models.CharField(max_length=10, unique=True, blank=True, null=True)

    # Winner tracking
    winners = models.ManyToManyField(User, related_name='matches_won', blank=True)
    losers = models.ManyToManyField(User, related_name='matches_lost', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date_time']

    def save(self, *args, **kwargs):
        if not self.share_code:
            self.share_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        if not self.title:
            self.title = f"{self.get_match_type_display()} Match"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.date_time}"

    def get_match_datetime_start(self):
        """Get match start datetime as timezone-aware"""
        return self.date_time

    def get_match_datetime_end(self):
        """Get match end datetime"""
        from datetime import timedelta
        return self.date_time + timedelta(minutes=self.duration)

    def is_completed(self):
        """Check if match is completed based on date/time"""
        if self.status == 'completed':
            return True

        current_datetime = timezone.now()
        match_end = self.get_match_datetime_end()

        return match_end < current_datetime

    def is_in_progress(self):
        """Check if match is currently in progress"""
        if self.status == 'in_progress':
            return True

        current_datetime = timezone.now()
        match_start = self.get_match_datetime_start()
        match_end = self.get_match_datetime_end()

        return match_start <= current_datetime < match_end

    def update_status(self):
        """Update match status based on current conditions"""
        # Don't update if manually cancelled
        if self.status == 'cancelled':
            return

        current_datetime = timezone.now()
        match_start = self.get_match_datetime_start()
        match_end = self.get_match_datetime_end()
        accepted_count = self.get_accepted_participants_count()

        # Check if match has ended
        if match_end < current_datetime:
            if self.status != 'completed':
                self.status = 'completed'
                self.is_open = False
                self.save()

        # Check if match is in progress
        elif match_start <= current_datetime < match_end:
            if self.status not in ['in_progress', 'completed']:
                self.status = 'in_progress'
                self.is_open = False
                self.save()

        # Check if match is full (before it starts)
        elif accepted_count >= self.max_players and current_datetime < match_start:
            if self.status == 'open':
                self.status = 'full'
                self.is_open = False
                self.save()

        # Otherwise it should be open (if not started yet and not full)
        elif current_datetime < match_start and accepted_count < self.max_players:
            if self.status not in ['open', 'full'] and self.status != 'cancelled':
                self.status = 'open'
                self.is_open = True
                self.save()

    def get_accepted_participants_count(self):
        """Get count of accepted participants including organizer"""
        # Count the participants (organizer is already included as a participant)
        return self.participants.filter(status='confirmed').count()

    def get_location_info(self):
        """Get match location info matching Flutter MatchLocation"""
        return {
            'club_name': self.club.name,
            'court_name': self.court.name,
            'address': self.club.address,
            'latitude': float(self.club.latitude),
            'longitude': float(self.club.longitude)
        }

    def mark_winners(self, winner_ids, loser_ids):
        """Mark individual winners and losers and update player stats (idempotent)"""
        if self.status != 'completed':
            return False

        # Get current winners and losers to decrement their stats first
        old_winners = set(self.winners.all().values_list('id', flat=True))
        old_losers = set(self.losers.all().values_list('id', flat=True))

        # Match duration in minutes (convert to hours for storage)
        match_hours = round(self.duration / 60, 1)

        # Decrement stats for users who were previously counted
        for user_id in old_winners:
            user = User.objects.get(id=user_id)
            if hasattr(user, 'stats'):
                user.stats.matches_played = max(0, user.stats.matches_played - 1)
                user.stats.matches_won = max(0, user.stats.matches_won - 1)
                user.stats.total_hours = max(0, user.stats.total_hours - match_hours)
                user.stats.save()

        for user_id in old_losers:
            user = User.objects.get(id=user_id)
            if hasattr(user, 'stats'):
                user.stats.matches_played = max(0, user.stats.matches_played - 1)
                user.stats.matches_lost = max(0, user.stats.matches_lost - 1)
                user.stats.total_hours = max(0, user.stats.total_hours - match_hours)
                user.stats.save()

        # Clear existing winners/losers
        self.winners.clear()
        self.losers.clear()

        # Add winners
        for user_id in winner_ids:
            user = User.objects.get(id=user_id)
            self.winners.add(user)
            # Update winner stats
            if hasattr(user, 'stats'):
                user.stats.matches_played += 1
                user.stats.matches_won += 1
                user.stats.total_hours += match_hours
                user.stats.save()

        # Add losers
        for user_id in loser_ids:
            user = User.objects.get(id=user_id)
            self.losers.add(user)
            # Update loser stats
            if hasattr(user, 'stats'):
                user.stats.matches_played += 1
                user.stats.matches_lost += 1
                user.stats.total_hours += match_hours
                user.stats.save()

        return True


class MatchParticipant(models.Model):
    """Player slot in a match matching Flutter PlayerSlot"""
    STATUS_CHOICES = [
        ('empty', 'Empty'),
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_participations', null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='empty')

    # Payment info
    amount_paid = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_intent_id = models.CharField(max_length=200, blank=True)

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['match', 'user']
        ordering = ['joined_at']

    def __str__(self):
        if self.user:
            return f"{self.user.username} in {self.match.title}"
        return f"Empty slot in {self.match.title}"


class MatchMessage(models.Model):
    """Chat messages within a match"""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username} in {self.match.title}: {self.content[:50]}"


class Rating(models.Model):
    """Player rating system"""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='ratings')
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    rated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('match', 'rater', 'rated_user')

    def __str__(self):
        return f"{self.rater.username} rated {self.rated_user.username}: {self.rating}/10"


class CourtRating(models.Model):
    """Court rating system"""
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='ratings')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='court_ratings')
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='court_ratings_given')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('court', 'match', 'rater')

    def __str__(self):
        return f"{self.rater.username} rated {self.court.name}: {self.rating}/5"


class Notification(models.Model):
    """User notifications"""
    TYPE_CHOICES = [
        ('match_invite', 'Match Invitation'),
        ('match_reminder', 'Match Reminder'),
        ('match_accepted', 'Match Accepted'),
        ('match_cancelled', 'Match Cancelled'),
        ('friend_request', 'Friend Request'),
        ('friend_accepted', 'Friend Request Accepted'),
        ('achievement', 'Achievement Unlocked'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, null=True, blank=True)
    friend_request = models.ForeignKey('FriendRequest', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} for {self.user.username}"


class CommunityPost(models.Model):
    """Community forum posts"""
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('tips', 'Tips & Tricks'),
        ('tournaments', 'Tournaments'),
        ('equipment', 'Equipment'),
        ('clubs', 'Clubs'),
        ('looking_for_players', 'Looking for Players'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    group = models.ForeignKey('CommunityGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def reply_count(self):
        return self.replies.count()


class PostReply(models.Model):
    """Replies to community posts"""
    post = models.ForeignKey(CommunityPost, on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_replies')
    content = models.TextField()
    parent_reply = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='child_replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(User, related_name='liked_replies', blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply to {self.post.title} by {self.author.username}"

    @property
    def like_count(self):
        return self.likes.count()


class CommunityGroup(models.Model):
    """Community groups/clubs"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    theme = models.CharField(max_length=50)  # e.g., "beginners", "tournaments", "technique"
    city = models.CharField(max_length=100, blank=True)
    club = models.ForeignKey('Club', on_delete=models.SET_NULL, null=True, blank=True, related_name='community_groups')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='community_groups')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class FriendRequest(models.Model):
    """Friend request system"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"


class Friendship(models.Model):
    """Friendship relationships"""
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"{self.user1.username} & {self.user2.username}"

    @classmethod
    def are_friends(cls, user1, user2):
        from django.db.models import Q
        return cls.objects.filter(
            Q(user1=user1, user2=user2) |
            Q(user1=user2, user2=user1)
        ).exists()

    @classmethod
    def get_friends(cls, user):
        from django.db.models import Q
        friendships = cls.objects.filter(
            Q(user1=user) | Q(user2=user)
        )
        friends = []
        for friendship in friendships:
            if friendship.user1 == user:
                friends.append(friendship.user2)
            else:
                friends.append(friendship.user1)
        return friends


class PrivateMessage(models.Model):
    """Direct messages between users"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username} to {self.receiver.username}: {self.content[:50]}"


class BlockedUser(models.Model):
    """User blocking system"""
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"

    @classmethod
    def is_blocked(cls, user1, user2):
        """Check if either user has blocked the other"""
        from django.db.models import Q
        return cls.objects.filter(
            Q(blocker=user1, blocked=user2) |
            Q(blocker=user2, blocked=user1)
        ).exists()

    @classmethod
    def get_blocked_user_ids(cls, user):
        """Get list of user IDs that are blocked by or have blocked the given user"""
        from django.db.models import Q
        blocked_relationships = cls.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        )
        blocked_ids = set()
        for rel in blocked_relationships:
            if rel.blocker == user:
                blocked_ids.add(rel.blocked_id)
            else:
                blocked_ids.add(rel.blocker_id)
        return list(blocked_ids)


class SavedClub(models.Model):
    """User saved/favorite clubs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_clubs')
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='saved_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'club')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} saved {self.club.name}"


# Signal handlers to create Profile and PlayerStats automatically
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create Profile when a new user is created"""
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def create_user_stats(sender, instance, created, **kwargs):
    """Create PlayerStats when a new user is created"""
    if created:
        PlayerStats.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save Profile when user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()