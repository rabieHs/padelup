from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Count
from django.utils import timezone
from datetime import datetime, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.pagination import PageNumberPagination

from .models import (
    Profile, PlayerStats, Club, Court, Booking, Match, MatchParticipant,
    MatchMessage, Rating, CourtRating, Notification, CommunityPost,
    PostReply, CommunityGroup, FriendRequest, Friendship, PrivateMessage,
    BlockedUser
)
from .serializers import (
    UserSerializer, ProfileSerializer, ProfileSetupSerializer, ProfileUpdateSerializer,
    PlayerStatsSerializer, ClubSerializer, CourtSerializer, BookingSerializer,
    MatchSerializer, MatchDetailSerializer, MatchParticipantSerializer,
    MatchMessageSerializer, RatingSerializer, CourtRatingSerializer,
    NotificationSerializer, CommunityPostSerializer, PostReplySerializer,
    CommunityGroupSerializer, FriendRequestSerializer, FriendshipSerializer,
    PrivateMessageSerializer, BlockedUserSerializer, RegisterSerializer,
    LoginSerializer, UserDetailSerializer
)


# ============================================================================
# AUTHENTICATION APIs
# ============================================================================

class RegisterView(APIView):
    """User registration API"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Create auth token
            token, created = Token.objects.get_or_create(user=user)
            # Return user data with token
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key,
                'message': 'Registration successful'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """User login API"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data.get('email')
            username = serializer.validated_data.get('username')
            password = serializer.validated_data.get('password')

            # Try to authenticate with email or username
            user = None
            if email:
                try:
                    user_obj = User.objects.get(email=email)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            elif username:
                user = authenticate(username=username, password=password)

            if user:
                login(request, user)
                token, created = Token.objects.get_or_create(user=user)
                return Response({
                    'user': UserSerializer(user).data,
                    'profile': ProfileSerializer(user.profile).data if hasattr(user, 'profile') else None,
                    'token': token.key,
                    'message': 'Login successful'
                }, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """User logout API"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delete auth token
        try:
            request.user.auth_token.delete()
        except:
            pass
        logout(request)
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)


class ProfileSetupView(APIView):
    """Profile setup after registration"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        serializer = ProfileSetupSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'profile': ProfileSerializer(profile).data,
                'message': 'Profile setup completed'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# USER PROFILE APIs
# ============================================================================

class ProfileView(APIView):
    """User profile API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current user's profile"""
        user = request.user
        return Response({
            'user': UserSerializer(user).data,
            'profile': ProfileSerializer(user.profile, context={'request': request}).data if hasattr(user, 'profile') else None,
            'stats': PlayerStatsSerializer(user.stats).data if hasattr(user, 'stats') else None
        }, status=status.HTTP_200_OK)

    def put(self, request):
        """Update current user's profile"""
        profile = request.user.profile
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'profile': ProfileSerializer(profile, context={'request': request}).data,
                'message': 'Profile updated successfully'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Delete user account and all associated data"""
        user = request.user

        # Delete auth token
        try:
            user.auth_token.delete()
        except:
            pass

        # Django will cascade delete all related data (matches, bookings, ratings, etc.)
        # due to foreign key relationships
        user.delete()

        return Response({'message': 'Account deleted successfully'}, status=status.HTTP_200_OK)


class PublicProfileView(APIView):
    """View other user's public profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)

            # Check if blocked
            if BlockedUser.is_blocked(request.user, user):
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

            # Build response
            data = {
                'user': UserSerializer(user).data,
                'profile': ProfileSerializer(user.profile, context={'request': request}).data if hasattr(user, 'profile') else None,
                'stats': PlayerStatsSerializer(user.stats).data if hasattr(user, 'stats') else None,
                'is_friend': Friendship.are_friends(request.user, user),
                'is_blocked': False,
                'is_own_profile': user.id == request.user.id
            }

            # Add friend request status if applicable
            friend_request = FriendRequest.objects.filter(
                Q(sender=request.user, receiver=user) |
                Q(sender=user, receiver=request.user),
                status='pending'
            ).first()

            if friend_request:
                data['friend_request'] = FriendRequestSerializer(friend_request).data

            return Response(data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# CLUB APIs
# ============================================================================

class ClubListView(APIView):
    """List and search clubs"""
    permission_classes = [AllowAny]  # Allow public access to clubs

    def get(self, request):
        # Get query parameters
        search = request.query_params.get('search', '')
        city = request.query_params.get('city', '')
        is_partner = request.query_params.get('is_partner', '')
        min_rating = request.query_params.get('min_rating', '')
        lat = request.query_params.get('lat', '')
        lng = request.query_params.get('lng', '')
        max_distance = request.query_params.get('max_distance', '')

        # Base queryset
        clubs = Club.objects.all()

        # Apply filters
        if search:
            clubs = clubs.filter(
                Q(name__icontains=search) |
                Q(address__icontains=search) |
                Q(city__icontains=search)
            )

        if city:
            clubs = clubs.filter(city__icontains=city)

        if is_partner:
            clubs = clubs.filter(is_partner=is_partner.lower() == 'true')

        if min_rating:
            clubs = clubs.filter(rating__gte=float(min_rating))

        # Sort by distance if coordinates provided
        if lat and lng:
            try:
                from math import radians, cos, sin, asin, sqrt

                def haversine_distance(lat1, lon1, lat2, lon2):
                    """Calculate the great circle distance between two points on Earth"""
                    # Convert decimal degrees to radians
                    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

                    # Haversine formula
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * asin(sqrt(a))
                    # Radius of Earth in kilometers
                    r = 6371
                    return c * r

                user_lat = float(lat)
                user_lng = float(lng)

                # Calculate distance for each club
                clubs_with_distance = []
                for club in clubs:
                    distance = haversine_distance(
                        user_lat, user_lng,
                        float(club.latitude), float(club.longitude)
                    )
                    clubs_with_distance.append((club, distance))

                # Sort by distance
                clubs_with_distance.sort(key=lambda x: x[1])

                # Filter by max_distance if provided
                if max_distance:
                    max_dist = float(max_distance)
                    clubs_with_distance = [(c, d) for c, d in clubs_with_distance if d <= max_dist]

                # Extract clubs and add distance to each
                clubs = [club for club, _ in clubs_with_distance]
                for club, distance in clubs_with_distance:
                    club.distance = round(distance, 2)

            except (ValueError, TypeError) as e:
                # If there's an error with coordinates, just continue without filtering
                pass

        # Paginate
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(clubs, request)

        serializer = ClubSerializer(result_page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Create a new club (admin dashboard)"""
        # Allow creation from admin dashboard without authentication
        serializer = ClubSerializer(data=request.data)
        if serializer.is_valid():
            club = serializer.save()
            return Response(ClubSerializer(club).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClubDetailView(APIView):
    """Club detail API"""
    permission_classes = [AllowAny]  # Allow access for admin dashboard

    def get(self, request, club_id):
        """Get club details"""
        try:
            club = Club.objects.get(id=club_id)
            serializer = ClubSerializer(club, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, club_id):
        """Update club (admin dashboard)"""
        try:
            club = Club.objects.get(id=club_id)
            serializer = ClubSerializer(club, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, club_id):
        """Patch club (for image uploads from admin dashboard)"""
        try:
            club = Club.objects.get(id=club_id)
            serializer = ClubSerializer(club, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, club_id):
        """Delete club (admin dashboard)"""
        try:
            club = Club.objects.get(id=club_id)
            club.delete()
            return Response({'message': 'Club deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# COURT APIs
# ============================================================================

class CourtListView(APIView):
    """List courts by club"""
    permission_classes = [AllowAny]  # Allow access for admin dashboard

    def get(self, request, club_id):
        """Get all courts for a club"""
        try:
            club = Club.objects.get(id=club_id)
            courts = Court.objects.filter(club=club)
            serializer = CourtSerializer(courts, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, club_id):
        """Create a new court (admin dashboard)"""
        try:
            club = Club.objects.get(id=club_id)
            serializer = CourtSerializer(data=request.data)
            if serializer.is_valid():
                court = serializer.save(club=club)
                return Response(CourtSerializer(court).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)


class CourtDetailView(APIView):
    """Court detail API"""
    permission_classes = [AllowAny]  # Allow access for admin dashboard

    def get(self, request, court_id):
        """Get court details"""
        try:
            court = Court.objects.get(id=court_id)
            serializer = CourtSerializer(court)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Court.DoesNotExist:
            return Response({'error': 'Court not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, court_id):
        """Update court (admin dashboard)"""
        try:
            court = Court.objects.get(id=court_id)
            serializer = CourtSerializer(court, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Court.DoesNotExist:
            return Response({'error': 'Court not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, court_id):
        """Delete court (admin dashboard)"""
        try:
            court = Court.objects.get(id=court_id)
            court.delete()
            return Response({'message': 'Court deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Court.DoesNotExist:
            return Response({'error': 'Court not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# BOOKING APIs
# ============================================================================

class BookingListView(APIView):
    """List and create bookings"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's bookings"""
        status_filter = request.query_params.get('status', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')

        bookings = Booking.objects.filter(user=request.user)

        if status_filter:
            bookings = bookings.filter(status=status_filter)

        if date_from:
            bookings = bookings.filter(date__gte=date_from)

        if date_to:
            bookings = bookings.filter(date__lte=date_to)

        bookings = bookings.order_by('-date', '-start_time')

        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new booking"""
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            # Check for conflicts
            court_id = serializer.validated_data['court'].id
            date = serializer.validated_data['date']
            start_time = serializer.validated_data['start_time']

            existing = Booking.objects.filter(
                court_id=court_id,
                date=date,
                start_time=start_time,
                status__in=['confirmed', 'pending']
            ).exists()

            if existing:
                return Response({'error': 'Time slot already booked'}, status=status.HTTP_400_BAD_REQUEST)

            booking = serializer.save(user=request.user)
            return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookingDetailView(APIView):
    """Booking detail API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        """Get booking details"""
        try:
            booking = Booking.objects.get(id=booking_id)
            # Check permission
            if booking.user != request.user and not request.user.is_staff:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            serializer = BookingSerializer(booking)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, booking_id):
        """Update booking status"""
        try:
            booking = Booking.objects.get(id=booking_id)
            # Check permission
            if booking.user != request.user and not request.user.is_staff:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            new_status = request.data.get('status')
            if new_status in ['cancelled', 'confirmed']:
                booking.status = new_status
                booking.save()
                return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, booking_id):
        """Cancel booking"""
        try:
            booking = Booking.objects.get(id=booking_id)
            # Check permission
            if booking.user != request.user and not request.user.is_staff:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            booking.status = 'cancelled'
            booking.save()
            return Response({'message': 'Booking cancelled successfully'}, status=status.HTTP_200_OK)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# MATCH APIs
# ============================================================================

class MatchListView(APIView):
    """List and create matches"""
    permission_classes = [AllowAny]  # Allow public access to view matches

    def get(self, request):
        """Get matches with filters"""
        # Get filters
        status_filter = request.query_params.get('status', '')
        match_type = request.query_params.get('type', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        club_id = request.query_params.get('club_id', '')
        skill_level = request.query_params.get('skill_level', '')
        my_matches = request.query_params.get('my_matches', '')
        search = request.query_params.get('search', '')  # Add search parameter

        # Get blocked user IDs (only if authenticated)
        if request.user.is_authenticated:
            blocked_user_ids = BlockedUser.get_blocked_user_ids(request.user)
        else:
            blocked_user_ids = []

        # Base queryset - exclude blocked users
        matches = Match.objects.exclude(organizer_id__in=blocked_user_ids)

        # Apply filters
        if status_filter:
            matches = matches.filter(status=status_filter)
        else:
            # By default, don't show cancelled matches
            matches = matches.exclude(status='cancelled')

        if match_type:
            matches = matches.filter(match_type=match_type)

        if date_from:
            # Handle both date and datetime formats
            if 'T' in date_from:
                # ISO datetime format, extract just the date
                date_from = date_from.split('T')[0]
            matches = matches.filter(date_time__date__gte=date_from)

        if date_to:
            # Handle both date and datetime formats
            if 'T' in date_to:
                # ISO datetime format, extract just the date
                date_to = date_to.split('T')[0]
            matches = matches.filter(date_time__date__lte=date_to)

        if club_id:
            matches = matches.filter(club_id=club_id)

        if skill_level and skill_level.isdigit():
            level = int(skill_level)
            matches = matches.filter(min_skill_level__lte=level, max_skill_level__gte=level)

        # Add search functionality (search by club name or location)
        if search:
            matches = matches.filter(
                Q(title__icontains=search) |
                Q(club__name__icontains=search) |
                Q(club__city__icontains=search) |
                Q(club__address__icontains=search)
            )

        if my_matches == 'true' and request.user.is_authenticated:
            # Get matches where user is organizer or participant
            participant_matches = MatchParticipant.objects.filter(
                user=request.user,
                status='confirmed'
            ).values_list('match_id', flat=True)

            matches = matches.filter(
                Q(organizer=request.user) | Q(id__in=participant_matches)
            )
        else:
            # For available matches (not my matches), only show public matches
            matches = matches.filter(is_public=True)
            # For non-authenticated users, only show open matches
            if not request.user.is_authenticated:
                matches = matches.filter(status='open')

        # Update match statuses
        for match in matches:
            match.update_status()

        # Order by date
        matches = matches.order_by('date_time')

        # Paginate
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(matches, request)

        serializer = MatchSerializer(result_page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Create a new match - Requires authentication"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required to create matches'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = MatchSerializer(data=request.data)
        if serializer.is_valid():
            match = serializer.save(organizer=request.user)
            # Pass context when serializing the response
            response_serializer = MatchSerializer(match, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MatchDetailView(APIView):
    """Match detail API"""
    permission_classes = [AllowAny]  # Allow public access to view match details

    def get(self, request, match_id):
        """Get match details"""
        try:
            match = Match.objects.get(id=match_id)
            match.update_status()

            serializer = MatchDetailSerializer(match, context={'request': request})
            data = serializer.data

            # Add user-specific info only if authenticated
            if request.user.is_authenticated:
                data['is_organizer'] = match.organizer == request.user
                data['is_participant'] = MatchParticipant.objects.filter(
                    match=match,
                    user=request.user,
                    status='confirmed'
                ).exists()
            else:
                data['is_organizer'] = False
                data['is_participant'] = False
                data['requires_login'] = True

            return Response(data, status=status.HTTP_200_OK)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, match_id):
        """Update match (organizer only)"""
        try:
            match = Match.objects.get(id=match_id)

            # Check permission
            if match.organizer != request.user:
                return Response({'error': 'Only organizer can update match'}, status=status.HTTP_403_FORBIDDEN)

            # Handle special actions
            action = request.data.get('action')
            if action == 'cancel':
                match.status = 'cancelled'
                match.is_open = False
                match.save()

                # Notify participants
                for participant in match.participants.filter(status='confirmed'):
                    Notification.objects.create(
                        user=participant.user,
                        type='match_cancelled',
                        match=match,
                        message=f'Match "{match.title}" has been cancelled'
                    )

                return Response({'message': 'Match cancelled successfully'}, status=status.HTTP_200_OK)

            # Regular update
            serializer = MatchSerializer(match, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, match_id):
        """Delete match (organizer only)"""
        try:
            match = Match.objects.get(id=match_id)

            # Check permission
            if match.organizer != request.user:
                return Response({'error': 'Only organizer can delete match'}, status=status.HTTP_403_FORBIDDEN)

            match.delete()
            return Response({'message': 'Match deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)


class MatchJoinView(APIView):
    """Join/leave match"""
    permission_classes = [IsAuthenticated]

    def post(self, request, match_id):
        """Join a match"""
        try:
            match = Match.objects.get(id=match_id)

            # Check if match is open
            if match.status != 'open':
                return Response({'error': 'Match is not open for joining'}, status=status.HTTP_400_BAD_REQUEST)

            # Check skill level
            user_skill = request.user.profile.skill_level if hasattr(request.user, 'profile') else 5
            if user_skill < match.min_skill_level or user_skill > match.max_skill_level:
                return Response({'error': 'Your skill level does not match requirements'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if already joined
            existing = MatchParticipant.objects.filter(match=match, user=request.user).first()
            if existing:
                if existing.status == 'confirmed':
                    return Response({'error': 'Already joined this match'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Update status
                    existing.status = 'confirmed'
                    existing.save()
                    return Response(MatchParticipantSerializer(existing).data, status=status.HTTP_200_OK)

            # Create participant
            participant = MatchParticipant.objects.create(
                match=match,
                user=request.user,
                status='confirmed'
            )

            # Update match status if full
            if match.get_accepted_participants_count() >= match.max_players:
                match.status = 'full'
                match.is_open = False
                match.save()

            # Notify organizer
            Notification.objects.create(
                user=match.organizer,
                type='match_accepted',
                match=match,
                message=f'{request.user.username} joined your match "{match.title}"'
            )

            return Response(MatchParticipantSerializer(participant).data, status=status.HTTP_201_CREATED)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, match_id):
        """Leave a match"""
        try:
            match = Match.objects.get(id=match_id)
            participant = MatchParticipant.objects.filter(match=match, user=request.user).first()

            if not participant:
                return Response({'error': 'Not a participant in this match'}, status=status.HTTP_400_BAD_REQUEST)

            participant.delete()

            # Update match status if was full
            if match.status == 'full':
                match.status = 'open'
                match.is_open = True
                match.save()

            return Response({'message': 'Left match successfully'}, status=status.HTTP_200_OK)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)


class MatchParticipantManageView(APIView):
    """Manage match participants (organizer only)"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, match_id, participant_id):
        """Remove participant from match (organizer only)"""
        try:
            match = Match.objects.get(id=match_id)

            # Check if user is organizer
            if match.organizer != request.user:
                return Response({'error': 'Only organizer can remove participants'}, status=status.HTTP_403_FORBIDDEN)

            # Find and remove participant
            participant = MatchParticipant.objects.filter(
                match=match,
                user_id=participant_id
            ).first()

            if not participant:
                return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)

            # Notify the removed participant
            Notification.objects.create(
                user_id=participant_id,
                type='removed_from_match',
                match=match,
                message=f'You have been removed from match "{match.title}"'
            )

            participant.delete()

            # Update match status if was full
            if match.status == 'full':
                match.status = 'open'
                match.is_open = True
                match.save()

            return Response({'message': 'Participant removed successfully'}, status=status.HTTP_200_OK)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)


class MatchInviteView(APIView):
    """Invite friends to a match"""
    permission_classes = [IsAuthenticated]

    def post(self, request, match_id):
        """Invite multiple friends to a match"""
        try:
            match = Match.objects.get(id=match_id)

            # Only organizer can invite friends
            if match.organizer != request.user:
                return Response({'error': 'Only organizer can invite friends'}, status=status.HTTP_403_FORBIDDEN)

            # Get friend IDs from request
            friend_ids = request.data.get('friend_ids', [])

            if not friend_ids:
                return Response({'error': 'No friends specified'}, status=status.HTTP_400_BAD_REQUEST)

            # Convert string IDs to integers if needed
            try:
                friend_ids = [int(fid) if isinstance(fid, str) else fid for fid in friend_ids]
            except (ValueError, TypeError):
                return Response({'error': 'Invalid user ID format'}, status=status.HTTP_400_BAD_REQUEST)

            results = []
            invited_count = 0

            for friend_id in friend_ids:
                try:
                    friend = User.objects.get(id=friend_id)

                    # Check if they are friends
                    if not Friendship.are_friends(request.user, friend):
                        results.append({
                            'user_id': friend_id,
                            'username': friend.username,
                            'success': False,
                            'error': 'Not friends with this user'
                        })
                        continue

                    # Check if already a participant
                    is_participant = MatchParticipant.objects.filter(
                        match=match,
                        user=friend,
                        status='confirmed'
                    ).exists()

                    if is_participant or friend == match.organizer:
                        results.append({
                            'user_id': friend_id,
                            'username': friend.username,
                            'success': False,
                            'error': 'Already in the match'
                        })
                        continue

                    # Check if already invited (has unread notification)
                    existing_invite = Notification.objects.filter(
                        user=friend,
                        match=match,
                        type='match_invite',
                        is_read=False
                    ).exists()

                    if existing_invite:
                        results.append({
                            'user_id': friend_id,
                            'username': friend.username,
                            'success': False,
                            'error': 'Already invited'
                        })
                        continue

                    # Create notification
                    Notification.objects.create(
                        user=friend,
                        type='match_invite',
                        match=match,
                        message=f'{request.user.username} invited you to join "{match.title}"'
                    )

                    results.append({
                        'user_id': friend_id,
                        'username': friend.username,
                        'success': True
                    })
                    invited_count += 1

                except User.DoesNotExist:
                    results.append({
                        'user_id': friend_id,
                        'success': False,
                        'error': 'User not found'
                    })

            return Response({
                'message': f'Invited {invited_count} friend(s) successfully',
                'invited_count': invited_count,
                'total_requested': len(friend_ids),
                'results': results
            }, status=status.HTTP_200_OK)

        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)


class MatchChatView(APIView):
    """Match chat messages"""
    permission_classes = [IsAuthenticated]

    def get(self, request, match_id):
        """Get match chat messages"""
        try:
            match = Match.objects.get(id=match_id)

            # Check if user is participant or organizer
            is_participant = MatchParticipant.objects.filter(
                match=match,
                user=request.user,
                status='confirmed'
            ).exists()

            if not (match.organizer == request.user or is_participant):
                return Response({'error': 'Not authorized to view chat'}, status=status.HTTP_403_FORBIDDEN)

            messages = match.messages.all().order_by('created_at')
            serializer = MatchMessageSerializer(messages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, match_id):
        """Send message in match chat"""
        try:
            match = Match.objects.get(id=match_id)

            # Check if user is participant or organizer
            is_participant = MatchParticipant.objects.filter(
                match=match,
                user=request.user,
                status='confirmed'
            ).exists()

            if not (match.organizer == request.user or is_participant):
                return Response({'error': 'Not authorized to send messages'}, status=status.HTTP_403_FORBIDDEN)

            content = request.data.get('content')
            if not content:
                return Response({'error': 'Message content required'}, status=status.HTTP_400_BAD_REQUEST)

            message = MatchMessage.objects.create(
                match=match,
                sender=request.user,
                content=content
            )

            serializer = MatchMessageSerializer(message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)


class MatchFinishView(APIView):
    """Mark match as finished/completed with winners and losers"""
    permission_classes = [IsAuthenticated]

    def post(self, request, match_id):
        """Finish a match and mark winners/losers"""
        try:
            match = Match.objects.get(id=match_id)

            # Only organizer can finish the match
            if match.organizer != request.user:
                return Response({'error': 'Only organizer can finish the match'}, status=status.HTTP_403_FORBIDDEN)

            # Check if match time has passed or is in progress
            if not (match.is_in_progress() or match.is_completed()):
                return Response({'error': 'Match has not started yet'}, status=status.HTTP_400_BAD_REQUEST)

            # Get winner and loser IDs from request
            winner_ids = request.data.get('winner_ids', [])
            loser_ids = request.data.get('loser_ids', [])

            # Convert string IDs to integers (frontend sends strings)
            try:
                winner_ids = [int(wid) if isinstance(wid, str) else wid for wid in winner_ids]
                loser_ids = [int(lid) if isinstance(lid, str) else lid for lid in loser_ids]
            except (ValueError, TypeError):
                return Response({'error': 'Invalid user ID format'}, status=status.HTTP_400_BAD_REQUEST)

            # Validate that all IDs are participants
            all_participant_ids = list(
                match.participants.filter(status='confirmed').values_list('user_id', flat=True)
            )
            # Add organizer if not in participants
            if match.organizer.id not in all_participant_ids:
                all_participant_ids.append(match.organizer.id)

            for winner_id in winner_ids:
                if winner_id not in all_participant_ids:
                    return Response({'error': f'User {winner_id} is not a participant'}, status=status.HTTP_400_BAD_REQUEST)

            for loser_id in loser_ids:
                if loser_id not in all_participant_ids:
                    return Response({'error': f'User {loser_id} is not a participant'}, status=status.HTTP_400_BAD_REQUEST)

            # Mark match as completed
            match.status = 'completed'
            match.is_open = False
            match.save()

            # Mark winners and losers
            success = match.mark_winners(winner_ids, loser_ids)

            if success:
                # Notify all participants that match is finished
                for participant in match.participants.filter(status='confirmed'):
                    Notification.objects.create(
                        user=participant.user,
                        type='match_reminder',  # Using existing type
                        match=match,
                        message=f'Match "{match.title}" has been completed. Please rate other players!'
                    )

                return Response({
                    'message': 'Match marked as finished successfully',
                    'match_id': match.id,
                    'status': match.status
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to mark winners/losers'}, status=status.HTTP_400_BAD_REQUEST)

        except Match.DoesNotExist:
            return Response({'error': 'Match not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# RATING APIs
# ============================================================================

class PlayerRatingView(APIView):
    """Player rating API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get ratings"""
        match_id = request.query_params.get('match_id')
        user_id = request.query_params.get('user_id')

        if match_id:
            # Get ratings for a specific match
            ratings = Rating.objects.filter(match_id=match_id)
        elif user_id:
            # Get ratings for a specific user
            ratings = Rating.objects.filter(rated_user_id=user_id)
        else:
            # Get ratings received by current user
            ratings = Rating.objects.filter(rated_user=request.user)

        serializer = RatingSerializer(ratings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Rate a player"""
        # Debug logging
        print('=== Rating API Debug ===')
        print(f'Request data: {request.data}')
        print(f'Request user: {request.user.id} ({request.user.username})')

        serializer = RatingSerializer(data=request.data)
        if serializer.is_valid():
            match_id = serializer.validated_data['match'].id
            rated_user_id = serializer.validated_data['rated_user'].id
            print(f'Valid data - Match: {match_id}, Rated user: {rated_user_id}')

            # Check if match is completed
            match = Match.objects.get(id=match_id)
            if match.status != 'completed':
                return Response({'error': 'Can only rate after match is completed'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if user was in the match
            was_participant = (
                match.organizer == request.user or
                MatchParticipant.objects.filter(
                    match=match,
                    user=request.user,
                    status='confirmed'
                ).exists()
            )

            if not was_participant:
                return Response({'error': 'You were not in this match'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if already rated
            existing = Rating.objects.filter(
                match_id=match_id,
                rater=request.user,
                rated_user_id=rated_user_id
            ).exists()

            if existing:
                return Response({'error': 'Already rated this player for this match'}, status=status.HTTP_400_BAD_REQUEST)

            rating = serializer.save(rater=request.user)

            # Update rated user's public rating
            rated_user = User.objects.get(id=rated_user_id)
            if hasattr(rated_user, 'profile'):
                rated_user.profile.update_public_rating()

            print('Rating saved successfully')
            print('=== End Debug ===')
            return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)

        print(f'Serializer errors: {serializer.errors}')
        print('=== End Debug ===')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CourtRatingView(APIView):
    """Court rating API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get court ratings"""
        court_id = request.query_params.get('court_id')
        club_id = request.query_params.get('club_id')

        if court_id:
            ratings = CourtRating.objects.filter(court_id=court_id)
        elif club_id:
            ratings = CourtRating.objects.filter(court__club_id=club_id)
        else:
            ratings = CourtRating.objects.filter(rater=request.user)

        serializer = CourtRatingSerializer(ratings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Rate a court"""
        serializer = CourtRatingSerializer(data=request.data)
        if serializer.is_valid():
            court_id = serializer.validated_data['court'].id
            match_id = serializer.validated_data['match'].id

            # Check if already rated
            existing = CourtRating.objects.filter(
                court_id=court_id,
                match_id=match_id,
                rater=request.user
            ).exists()

            if existing:
                return Response({'error': 'Already rated this court for this match'}, status=status.HTTP_400_BAD_REQUEST)

            rating = serializer.save(rater=request.user)

            # Update club rating
            court = Court.objects.get(id=court_id)
            court.club.update_rating()

            return Response(CourtRatingSerializer(rating).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# COMMUNITY APIs
# ============================================================================

class CommunityPostView(APIView):
    """Community posts API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get community posts"""
        category = request.query_params.get('category', '')
        city = request.query_params.get('city', '')
        group_id = request.query_params.get('group_id', '')

        posts = CommunityPost.objects.all()

        if category:
            posts = posts.filter(category=category)
        if city:
            posts = posts.filter(city__icontains=city)
        if group_id:
            posts = posts.filter(group_id=group_id)

        posts = posts.order_by('-created_at')

        # Paginate
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(posts, request)

        serializer = CommunityPostSerializer(result_page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Create a community post"""
        serializer = CommunityPostSerializer(data=request.data)
        if serializer.is_valid():
            post = serializer.save(author=request.user)
            return Response(CommunityPostSerializer(post, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostLikeView(APIView):
    """Like/unlike posts"""
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        """Toggle like on a post"""
        try:
            post = CommunityPost.objects.get(id=post_id)
            if post.likes.filter(id=request.user.id).exists():
                post.likes.remove(request.user)
                liked = False
            else:
                post.likes.add(request.user)
                liked = True

            return Response({
                'liked': liked,
                'like_count': post.like_count
            }, status=status.HTTP_200_OK)
        except CommunityPost.DoesNotExist:
            return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)


class PostReplyView(APIView):
    """Post replies API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        """Get replies for a post"""
        try:
            post = CommunityPost.objects.get(id=post_id)
            replies = post.replies.filter(parent_reply__isnull=True)
            serializer = PostReplySerializer(replies, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except CommunityPost.DoesNotExist:
            return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, post_id):
        """Create a reply"""
        try:
            post = CommunityPost.objects.get(id=post_id)
            content = request.data.get('content')
            parent_reply_id = request.data.get('parent_reply_id')

            if not content:
                return Response({'error': 'Content required'}, status=status.HTTP_400_BAD_REQUEST)

            reply = PostReply.objects.create(
                post=post,
                author=request.user,
                content=content,
                parent_reply_id=parent_reply_id if parent_reply_id else None
            )

            serializer = PostReplySerializer(reply, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except CommunityPost.DoesNotExist:
            return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# FRIEND SYSTEM APIs
# ============================================================================

class FriendRequestView(APIView):
    """Friend requests API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get friend requests"""
        # Get pending requests only
        received = FriendRequest.objects.filter(
            receiver=request.user,
            status='pending'
        )
        sent = FriendRequest.objects.filter(
            sender=request.user,
            status='pending'  # Only show pending sent requests
        )

        return Response({
            'received': FriendRequestSerializer(received, many=True).data,
            'sent': FriendRequestSerializer(sent, many=True).data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Send friend request"""
        receiver_id = request.data.get('receiver_id')
        message = request.data.get('message', '')

        try:
            receiver = User.objects.get(id=receiver_id)

            if receiver == request.user:
                return Response({'error': 'Cannot send friend request to yourself'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if already friends
            if Friendship.are_friends(request.user, receiver):
                return Response({'error': 'Already friends'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if request already exists
            existing = FriendRequest.objects.filter(
                Q(sender=request.user, receiver=receiver) |
                Q(sender=receiver, receiver=request.user)
            ).first()

            if existing:
                if existing.status == 'pending':
                    return Response({'error': 'Friend request already pending'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Delete old request (accepted/rejected) before creating new one
                    existing.delete()

            # Create friend request
            friend_request = FriendRequest.objects.create(
                sender=request.user,
                receiver=receiver,
                message=message
            )

            # Send notification
            Notification.objects.create(
                user=receiver,
                type='friend_request',
                friend_request=friend_request,
                message=f'{request.user.username} sent you a friend request'
            )

            return Response(FriendRequestSerializer(friend_request).data, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


class FriendRequestManageView(APIView):
    """Manage friend requests"""
    permission_classes = [IsAuthenticated]

    def put(self, request, request_id):
        """Accept/reject friend request"""
        action = request.data.get('action')  # 'accept' or 'reject'

        try:
            friend_request = FriendRequest.objects.get(
                id=request_id,
                receiver=request.user,
                status='pending'
            )

            if action == 'accept':
                # Create friendship
                Friendship.objects.create(
                    user1=min(friend_request.sender, friend_request.receiver, key=lambda u: u.id),
                    user2=max(friend_request.sender, friend_request.receiver, key=lambda u: u.id)
                )
                friend_request.status = 'accepted'
                friend_request.save()

                # Notify sender
                Notification.objects.create(
                    user=friend_request.sender,
                    type='friend_accepted',
                    friend_request=friend_request,
                    message=f'{request.user.username} accepted your friend request'
                )

                return Response({'message': 'Friend request accepted'}, status=status.HTTP_200_OK)

            elif action == 'reject':
                friend_request.status = 'rejected'
                friend_request.save()
                return Response({'message': 'Friend request rejected'}, status=status.HTTP_200_OK)

            else:
                return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)


class FriendsListView(APIView):
    """Friends list API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's friends"""
        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user)
        )

        serializer = FriendshipSerializer(friendships, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, friend_id):
        """Remove friend"""
        try:
            friend = User.objects.get(id=friend_id)

            friendship = Friendship.objects.filter(
                Q(user1=request.user, user2=friend) |
                Q(user1=friend, user2=request.user)
            ).first()

            if friendship:
                friendship.delete()
                return Response({'message': 'Friend removed'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Not friends'}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# NOTIFICATION APIs
# ============================================================================

class NotificationView(APIView):
    """Notifications API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's notifications"""
        unread_only = request.query_params.get('unread_only', 'false').lower() == 'true'

        notifications = Notification.objects.filter(user=request.user)

        if unread_only:
            notifications = notifications.filter(is_read=False)

        notifications = notifications.order_by('-created_at')[:50]

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        """Mark notifications as read"""
        notification_ids = request.data.get('notification_ids', [])

        if notification_ids:
            Notification.objects.filter(
                id__in=notification_ids,
                user=request.user
            ).update(is_read=True)
        else:
            # Mark all as read
            Notification.objects.filter(
                user=request.user,
                is_read=False
            ).update(is_read=True)

        return Response({'message': 'Notifications marked as read'}, status=status.HTTP_200_OK)


# ============================================================================
# LEADERBOARD & STATS APIs
# ============================================================================

class LeaderboardView(APIView):
    """Leaderboard API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get leaderboard"""
        city = request.query_params.get('city', '')
        club_id = request.query_params.get('club_id', '')
        limit = int(request.query_params.get('limit', 50))

        stats = PlayerStats.objects.select_related('user__profile')

        if city:
            stats = stats.filter(city__icontains=city)

        if club_id:
            # Get players who frequently play at this club
            stats = stats.filter(favorite_club_id=club_id)

        # Order by win rate and matches won
        stats = stats.order_by('-matches_won', '-matches_played')[:limit]

        serializer = PlayerStatsSerializer(stats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserStatsView(APIView):
    """User statistics API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id=None):
        """Get user stats"""
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            user = request.user

        if hasattr(user, 'stats'):
            serializer = PlayerStatsSerializer(user.stats)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Stats not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# USER MANAGEMENT API (Admin Dashboard)
# ============================================================================

class UserListView(APIView):
    """User list and management API for admin dashboard"""
    permission_classes = [AllowAny]  # Allow access for admin dashboard

    def get(self, request):
        """Get all users with profiles"""
        users = User.objects.select_related('profile').all().order_by('-date_joined')
        serializer = UserDetailSerializer(users, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserDetailManagementView(APIView):
    """User detail management API for admin dashboard"""
    permission_classes = [AllowAny]  # Allow access for admin dashboard

    def get(self, request, user_id):
        """Get user details"""
        try:
            user = User.objects.select_related('profile', 'stats').get(id=user_id)
            serializer = UserDetailSerializer(user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, user_id):
        """Update user status (e.g., activate/deactivate)"""
        try:
            user = User.objects.get(id=user_id)

            # Allow updating is_active status
            if 'is_active' in request.data:
                user.is_active = request.data['is_active']
                user.save()

            serializer = UserDetailSerializer(user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================================================
# USER SEARCH API
# ============================================================================

class UserSearchView(APIView):
    """Search users"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Search for users"""
        query = request.query_params.get('q', '')

        if len(query) < 2:
            return Response({'error': 'Query too short'}, status=status.HTTP_400_BAD_REQUEST)

        # Get blocked user IDs
        blocked_user_ids = BlockedUser.get_blocked_user_ids(request.user)

        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(
            Q(id=request.user.id) |
            Q(id__in=blocked_user_ids)
        )[:20]

        results = []
        for user in users:
            results.append({
                'id': user.id,
                'username': user.username,
                'full_name': f"{user.first_name} {user.last_name}".strip(),
                'avatar': user.profile.avatar.url if hasattr(user, 'profile') and user.profile.avatar else None,
                'skill_level': user.profile.skill_level if hasattr(user, 'profile') else None,
                'is_friend': Friendship.are_friends(request.user, user),
                'has_pending_request': FriendRequest.objects.filter(
                    Q(sender=request.user, receiver=user, status='pending') |
                    Q(sender=user, receiver=request.user, status='pending')
                ).exists()
            })

        return Response(results, status=status.HTTP_200_OK)


# ============================================================================
# SAVED CLUBS API
# ============================================================================

class SavedClubView(APIView):
    """Saved/favorite clubs API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's saved clubs"""
        from .models import SavedClub
        from .serializers import SavedClubSerializer

        saved_clubs = SavedClub.objects.filter(user=request.user).order_by('-created_at')
        serializer = SavedClubSerializer(saved_clubs, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Save/favorite a club"""
        from .models import SavedClub
        from .serializers import SavedClubSerializer

        club_id = request.data.get('club_id')

        if not club_id:
            return Response({'error': 'club_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            club = Club.objects.get(id=club_id)
        except Club.DoesNotExist:
            return Response({'error': 'Club not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if already saved
        saved_club, created = SavedClub.objects.get_or_create(
            user=request.user,
            club=club
        )

        if created:
            serializer = SavedClubSerializer(saved_club, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': 'Club already saved'}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Unsave/unfavorite a club"""
        from .models import SavedClub

        club_id = request.data.get('club_id')

        if not club_id:
            return Response({'error': 'club_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            saved_club = SavedClub.objects.get(user=request.user, club_id=club_id)
            saved_club.delete()
            return Response({'message': 'Club removed from favorites'}, status=status.HTTP_200_OK)
        except SavedClub.DoesNotExist:
            return Response({'error': 'Club not in favorites'}, status=status.HTTP_404_NOT_FOUND)