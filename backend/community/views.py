from django.db.models import Count, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Post, Comment
from .serializers import PostSerializer, CommentSerializer
from .services import toggle_post_like, toggle_comment_like

User = get_user_model()


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return (
            Post.objects
            .select_related('author')
            .annotate(like_count=Count('likes'))
            .order_by('-created_at')
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def list(self, request, *args, **kwargs):
        posts = self.get_queryset()
        post_ids = [p.id for p in posts]

        comments = (
            Comment.objects
            .filter(post_id__in=post_ids)
            .select_related('author', 'post', 'parent')
            .annotate(like_count=Count('likes'))
            .order_by('created_at')
        )

        comments_by_post = {}
        for c in comments:
            comments_by_post.setdefault(c.post_id, []).append(c)

        serializer = self.get_serializer(
            posts,
            many=True,
            context={'comments_by_post': comments_by_post},
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        liked = toggle_post_like(request.user, pk)
        post = self.get_queryset().get(pk=pk)
        return Response({'liked': liked, 'like_count': post.likes.count()})


class CommentViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    queryset = Comment.objects.all().select_related('author', 'post', 'parent')
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        liked = toggle_comment_like(request.user, pk)
        comment = (
            Comment.objects
            .filter(pk=pk)
            .annotate(like_count=Count('likes'))
            .get()
        )
        return Response({'liked': liked, 'like_count': comment.like_count})


class LeaderboardView(APIView):
    def get(self, request):
        now = timezone.now()
        window_start = now - timezone.timedelta(hours=24)
        leaderboard_qs = (
            User.objects
            .filter(karma_transactions__created_at__gte=window_start)
            .annotate(daily_karma=Sum('karma_transactions__amount'))
            .order_by('-daily_karma')[:5]
        )
        data = [
            {
                'user_id': u.id,
                'username': u.username,
                'daily_karma': u.daily_karma or 0,
            }
            for u in leaderboard_qs
        ]
        return Response(data)
