from django.db import transaction
from .models import Post, Comment, Like, KarmaTransaction

POST_KARMA = 5
COMMENT_KARMA = 1


@transaction.atomic
def toggle_post_like(user, post_id):
    post = Post.objects.select_for_update().get(id=post_id)
    like, created = Like.objects.get_or_create(user=user, post=post, comment=None)
    if not created:
        KarmaTransaction.objects.filter(source_like=like).delete()
        like.delete()
        return False
    KarmaTransaction.objects.create(
        user=post.author,
        amount=POST_KARMA,
        source_like=like,
    )
    return True


@transaction.atomic
def toggle_comment_like(user, comment_id):
    comment = Comment.objects.select_for_update().get(id=comment_id)
    like, created = Like.objects.get_or_create(user=user, comment=comment, post=None)
    if not created:
        KarmaTransaction.objects.filter(source_like=like).delete()
        like.delete()
        return False
    KarmaTransaction.objects.create(
        user=comment.author,
        amount=COMMENT_KARMA,
        source_like=like,
    )
    return True
