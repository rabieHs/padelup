from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    # Authentication
    RegisterView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ProfileSetupView,

    # User Profile
    ProfileView,
    PublicProfileView,

    # Clubs
    ClubListView,
    ClubDetailView,

    # Courts
    CourtListView,
    CourtDetailView,

    # Bookings
    BookingListView,
    BookingDetailView,

    # Matches
    MatchListView,
    MatchDetailView,
    MatchJoinView,
    MatchParticipantManageView,
    MatchInviteView,
    MatchChatView,
    MatchFinishView,

    # Ratings
    PlayerRatingView,
    CourtRatingView,

    # Community
    CommunityPostView,
    PostLikeView,
    PostReplyView,

    # Friends
    FriendRequestView,
    FriendRequestManageView,
    FriendsListView,

    # Notifications
    NotificationView,

    # Leaderboard & Stats
    LeaderboardView,
    UserStatsView,

    # User Management (Admin)
    UserListView,
    UserDetailManagementView,

    # Search
    UserSearchView,

    # Saved Clubs
    SavedClubView,
)

app_name = 'app'

urlpatterns = [
    # ============================================================================
    # AUTHENTICATION ENDPOINTS
    # ============================================================================
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('auth/profile-setup/', ProfileSetupView.as_view(), name='profile_setup'),

    # ============================================================================
    # USER PROFILE ENDPOINTS
    # ============================================================================
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:user_id>/', PublicProfileView.as_view(), name='public_profile'),

    # ============================================================================
    # CLUB ENDPOINTS
    # ============================================================================
    path('clubs/', ClubListView.as_view(), name='club_list'),
    path('clubs/<int:club_id>/', ClubDetailView.as_view(), name='club_detail'),

    # ============================================================================
    # COURT ENDPOINTS
    # ============================================================================
    path('clubs/<int:club_id>/courts/', CourtListView.as_view(), name='court_list'),
    path('courts/<int:court_id>/', CourtDetailView.as_view(), name='court_detail'),

    # ============================================================================
    # BOOKING ENDPOINTS
    # ============================================================================
    path('bookings/', BookingListView.as_view(), name='booking_list'),
    path('bookings/<int:booking_id>/', BookingDetailView.as_view(), name='booking_detail'),

    # ============================================================================
    # MATCH ENDPOINTS
    # ============================================================================
    path('matches/', MatchListView.as_view(), name='match_list'),
    path('matches/<int:match_id>/', MatchDetailView.as_view(), name='match_detail'),
    path('matches/<int:match_id>/join/', MatchJoinView.as_view(), name='match_join'),
    path('matches/<int:match_id>/participants/<int:participant_id>/', MatchParticipantManageView.as_view(), name='match_participant_manage'),
    path('matches/<int:match_id>/invite/', MatchInviteView.as_view(), name='match_invite'),
    path('matches/<int:match_id>/chat/', MatchChatView.as_view(), name='match_chat'),
    path('matches/<int:match_id>/finish/', MatchFinishView.as_view(), name='match_finish'),

    # ============================================================================
    # RATING ENDPOINTS
    # ============================================================================
    path('ratings/players/', PlayerRatingView.as_view(), name='player_rating'),
    path('ratings/courts/', CourtRatingView.as_view(), name='court_rating'),

    # ============================================================================
    # COMMUNITY ENDPOINTS
    # ============================================================================
    path('community/posts/', CommunityPostView.as_view(), name='community_posts'),
    path('community/posts/<int:post_id>/like/', PostLikeView.as_view(), name='post_like'),
    path('community/posts/<int:post_id>/replies/', PostReplyView.as_view(), name='post_replies'),

    # ============================================================================
    # FRIEND SYSTEM ENDPOINTS
    # ============================================================================
    path('friends/', FriendsListView.as_view(), name='friends_list'),
    path('friends/<int:friend_id>/', FriendsListView.as_view(), name='friend_remove'),
    path('friend-requests/', FriendRequestView.as_view(), name='friend_requests'),
    path('friend-requests/<int:request_id>/', FriendRequestManageView.as_view(), name='friend_request_manage'),

    # ============================================================================
    # NOTIFICATION ENDPOINTS
    # ============================================================================
    path('notifications/', NotificationView.as_view(), name='notifications'),

    # ============================================================================
    # LEADERBOARD & STATS ENDPOINTS
    # ============================================================================
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('stats/', UserStatsView.as_view(), name='user_stats'),
    path('stats/<int:user_id>/', UserStatsView.as_view(), name='user_stats_detail'),

    # ============================================================================
    # USER MANAGEMENT ENDPOINTS (Admin Dashboard)
    # ============================================================================
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:user_id>/', UserDetailManagementView.as_view(), name='user_detail_management'),

    # ============================================================================
    # SEARCH ENDPOINTS
    # ============================================================================
    path('users/search/', UserSearchView.as_view(), name='user_search'),

    # ============================================================================
    # SAVED CLUBS ENDPOINTS
    # ============================================================================
    path('saved-clubs/', SavedClubView.as_view(), name='saved_clubs'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""
API ENDPOINT DOCUMENTATION

AUTHENTICATION:
--------------
POST   /api/auth/register/           - Register new user
POST   /api/auth/login/              - Login user
POST   /api/auth/logout/             - Logout user
POST   /api/auth/profile-setup/      - Setup profile after registration

USER PROFILE:
------------
GET    /api/profile/                 - Get current user profile
PUT    /api/profile/                 - Update current user profile
DELETE /api/profile/                 - Delete user account
GET    /api/profile/{user_id}/       - Get public profile of user

CLUBS:
------
GET    /api/clubs/                   - List/search clubs
POST   /api/clubs/                   - Create club (admin)
GET    /api/clubs/{club_id}/         - Get club details
PUT    /api/clubs/{club_id}/         - Update club (admin)
DELETE /api/clubs/{club_id}/         - Delete club (admin)

COURTS:
-------
GET    /api/clubs/{club_id}/courts/  - List courts for club
POST   /api/clubs/{club_id}/courts/  - Create court (admin)
GET    /api/courts/{court_id}/       - Get court details
PUT    /api/courts/{court_id}/       - Update court (admin)
DELETE /api/courts/{court_id}/       - Delete court (admin)

BOOKINGS:
---------
GET    /api/bookings/                - List user bookings
POST   /api/bookings/                - Create new booking
GET    /api/bookings/{booking_id}/   - Get booking details
PUT    /api/bookings/{booking_id}/   - Update booking status
DELETE /api/bookings/{booking_id}/   - Cancel booking

MATCHES:
--------
GET    /api/matches/                 - List matches (filters: status, type, date_from, date_to, club_id, skill_level, my_matches)
POST   /api/matches/                 - Create new match
GET    /api/matches/{match_id}/      - Get match details
PUT    /api/matches/{match_id}/      - Update match (organizer only)
DELETE /api/matches/{match_id}/      - Delete match (organizer only)
POST   /api/matches/{match_id}/join/ - Join match
DELETE /api/matches/{match_id}/join/ - Leave match
DELETE /api/matches/{match_id}/participants/{participant_id}/ - Remove participant (organizer only)
POST   /api/matches/{match_id}/invite/ - Invite friends to match (organizer only)
GET    /api/matches/{match_id}/chat/ - Get match chat messages
POST   /api/matches/{match_id}/chat/ - Send message in match chat
POST   /api/matches/{match_id}/finish/ - Finish match and mark winners/losers (organizer only)

RATINGS:
--------
GET    /api/ratings/players/         - Get player ratings (filters: match_id, user_id)
POST   /api/ratings/players/         - Rate a player
GET    /api/ratings/courts/          - Get court ratings (filters: court_id, club_id)
POST   /api/ratings/courts/          - Rate a court

COMMUNITY:
----------
GET    /api/community/posts/         - List posts (filters: category, city, group_id)
POST   /api/community/posts/         - Create post
POST   /api/community/posts/{post_id}/like/    - Toggle like on post
GET    /api/community/posts/{post_id}/replies/ - Get post replies
POST   /api/community/posts/{post_id}/replies/ - Create reply

FRIENDS:
--------
GET    /api/friends/                 - Get friends list
DELETE /api/friends/{friend_id}/     - Remove friend
GET    /api/friend-requests/         - Get friend requests (sent & received)
POST   /api/friend-requests/         - Send friend request
PUT    /api/friend-requests/{id}/    - Accept/reject friend request

NOTIFICATIONS:
--------------
GET    /api/notifications/           - Get notifications (filter: unread_only)
PUT    /api/notifications/           - Mark notifications as read

LEADERBOARD & STATS:
-------------------
GET    /api/leaderboard/             - Get leaderboard (filters: city, club_id, limit)
GET    /api/stats/                   - Get current user stats
GET    /api/stats/{user_id}/         - Get specific user stats

SEARCH:
-------
GET    /api/users/search/            - Search users (param: q)

AUTHENTICATION:
--------------
All endpoints except registration and login require authentication via Token header:
Authorization: Token {token_key}
"""