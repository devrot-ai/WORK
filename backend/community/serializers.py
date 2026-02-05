from rest_framework import serializers
from .models import Post, Comment


class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id',
            'post',
            'author',
            'author_username',
            'parent',
            'content',
            'created_at',
            'like_count',
            'replies',
        ]
        read_only_fields = ['author', 'post', 'like_count', 'replies']

    def get_replies(self, obj):
        children = getattr(obj, '_cached_replies', [])
        return CommentSerializer(children, many=True).data


class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id',
            'author',
            'author_username',
            'content',
            'created_at',
            'like_count',
            'comments',
        ]
        read_only_fields = ['author', 'like_count', 'comments']

    def get_comments(self, obj):
        comments_by_post = self.context.get('comments_by_post', {})
        comments = comments_by_post.get(obj.id, [])

        comment_map = {c.id: c for c in comments}
        roots = []
        for c in comments:
            c._cached_replies = []
        for c in comments:
            if c.parent_id is None:
                roots.append(c)
            else:
                parent = comment_map.get(c.parent_id)
                if parent:
                    parent._cached_replies.append(c)
        return CommentSerializer(roots, many=True).data
