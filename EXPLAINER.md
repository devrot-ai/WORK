# EXPLAINER.md - Technical Deep Dive

## 1. The Tree: Nested Comments Database Design

### Database Model

I modeled nested comments using a **self-referential foreign key** on the `Comment` model:

```python
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

- `parent=None` indicates a top-level comment
- `parent=<id>` indicates a reply to another comment
- Added composite index on `(post, parent)` for efficient queries

### Avoiding N+1: The Tree-Building Strategy

The naive approach would serialize recursively, triggering a DB query for each node. Instead:

**Single Query Approach**:
```python
# Fetch ALL comments for the post list in one query
comments = (
    Comment.objects
    .filter(post_id__in=post_ids)
    .select_related('author', 'post', 'parent')
    .annotate(like_count=Count('likes'))
    .order_by('created_at')
)
```

**In-Memory Tree Construction**:
```python
comment_map = {c.id: c for c in comments}
roots = []

for c in comments:
    c._cached_replies = []  # Attach empty list

for c in comments:
    if c.parent_id is None:
        roots.append(c)  # Top-level
    else:
        parent = comment_map.get(c.parent_id)
        if parent:
            parent._cached_replies.append(c)  # Wire child to parent
```

**Result**: 
- 1 query for posts
- 1 query for all comments across all posts
- Tree built in Python (O(n) time)
- No recursive DB calls

---

## 2. The Math: Last 24-Hour Leaderboard Calculation

### The Challenge

The requirement was:
> "Calculate Karma dynamically from transaction history. Do NOT store a simple integer field."

### The Solution

**KarmaTransaction Model** (append-only ledger):
```python
class KarmaTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.IntegerField()  # +5 for post like, +1 for comment like
    source_like = models.OneToOneField(Like, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Leaderboard Query** (the actual SQL generated):

```python
now = timezone.now()
window_start = now - timezone.timedelta(hours=24)

leaderboard_qs = (
    User.objects
    .filter(karma_transactions__created_at__gte=window_start)
    .annotate(daily_karma=Sum('karma_transactions__amount'))
    .order_by('-daily_karma')[:5]
)
```

**Generated SQL**:
```sql
SELECT auth_user.id, 
       auth_user.username,
       SUM(community_karmatransaction.amount) AS daily_karma
FROM auth_user
INNER JOIN community_karmatransaction 
    ON auth_user.id = community_karmatransaction.user_id
WHERE community_karmatransaction.created_at >= '2026-02-04 21:00:00'
GROUP BY auth_user.id, auth_user.username
ORDER BY daily_karma DESC
LIMIT 5;
```

**Why This Works**:
- Time-windowed filter runs on indexed `created_at`
- Aggregates only transactions in the 24h window
- No cached "daily karma" field that would go stale
- Survives unlike/deletion gracefully (transaction deleted = karma reverted)

---

## 3. The AI Audit: Where AI Failed & My Fix

### **Bug #1: Missing Transaction Atomicity**

**AI-Generated Code (Broken)**:
```python
# services.py - AI's original
def toggle_post_like(user, post_id):
    like, created = Like.objects.get_or_create(user=user, post=post)
    if created:
        KarmaTransaction.objects.create(
            user=post.author,
            amount=5,
            source_like=like
        )
    else:
        KarmaTransaction.objects.filter(source_like=like).delete()
        like.delete()
```

**The Problem**: Race condition! Two users liking simultaneously could create duplicate `Like` objects because `get_or_create` isn't atomic without row-level locking.

**My Fix**:
```python
from django.db import transaction

@transaction.atomic
def toggle_post_like(user, post_id):
    post = Post.objects.select_for_update().get(id=post_id)  # Row lock
    like, created = Like.objects.get_or_create(user=user, post=post, comment=None)
    # ... rest of logic
```

- Added `@transaction.atomic` decorator
- Added `select_for_update()` to lock the Post row
- Now concurrent requests serialize properly

### **Bug #2: AI Forgot Unique Constraints on Like Model**

**AI-Generated Model (Incomplete)**:
```python
class Like(models.Model):
    user = models.ForeignKey(User)
    post = models.ForeignKey(Post, null=True)
    comment = models.ForeignKey(Comment, null=True)
```

**The Problem**: Nothing prevents a user from creating 100 likes on the same post by spamming the button.

**My Fix**:
```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['user', 'post'],
            condition=models.Q(post__isnull=False),
            name='unique_user_post_like'
        ),
        models.UniqueConstraint(
            fields=['user', 'comment'],
            condition=models.Q(comment__isnull=False),
            name='unique_user_comment_like'
        )
    ]
```

- Added DB-level unique constraints
- `condition=` ensures the constraint only applies when post/comment is set
- Database rejects duplicates even if app code fails

---

## Summary

- **Tree**: Self-FK + in-memory assembly = O(n) with 1 query
- **Math**: Time-windowed `SUM()` aggregate over ledger table
- **AI Mistakes**: Missing transactions + missing constraints = race conditions and data corruption

This architecture handles the N+1 problem, concurrency safely, and calculates leaderboard dynamically as required.
