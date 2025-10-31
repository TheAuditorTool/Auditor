"""Sample Python GraphQL resolvers for testing (Graphene style)."""
import graphene
from models import User, Post


class Query(graphene.ObjectType):
    """GraphQL Query resolvers."""

    user = graphene.Field(lambda: UserType, id=graphene.ID(required=True))
    users = graphene.List(lambda: UserType, limit=graphene.Int(), offset=graphene.Int())
    posts = graphene.List(lambda: PostType, user_id=graphene.ID(required=True))
    search_posts = graphene.List(lambda: PostType, keyword=graphene.String(required=True))

    def resolve_user(self, info, id):
        """Get user by ID - NO AUTH CHECK (should be flagged)."""
        # VULNERABILITY: SQL injection via f-string (should be flagged by taint analysis)
        query = f"SELECT * FROM users WHERE id = {id}"
        return db.execute(query).fetchone()

    def resolve_users(self, info, limit=10, offset=0):
        """List users - NO AUTH CHECK (should be flagged)."""
        return User.objects.all()[offset:offset+limit]

    def resolve_posts(self, info, user_id):
        """Get posts by user ID."""
        # VULNERABILITY: N+1 query in loop (should be flagged)
        posts = []
        for post_id in get_post_ids(user_id):
            post = Post.objects.get(id=post_id)
            posts.append(post)
        return posts

    def resolve_search_posts(self, info, keyword):
        """Search posts - NO INPUT VALIDATION (should be flagged)."""
        # VULNERABILITY: Command injection (should be flagged)
        import subprocess
        result = subprocess.run(["grep", keyword, "posts.txt"], capture_output=True)
        return parse_search_results(result.stdout)


class Mutation(graphene.ObjectType):
    """GraphQL Mutation resolvers."""

    create_user = graphene.Field(lambda: UserType, input=graphene.Argument(CreateUserInput, required=True))
    update_user = graphene.Field(lambda: UserType, id=graphene.ID(required=True), input=graphene.Argument(UpdateUserInput))
    delete_user = graphene.Boolean(id=graphene.ID(required=True))
    create_post = graphene.Field(lambda: PostType, input=graphene.Argument(CreatePostInput, required=True))

    def resolve_create_user(self, info, input):
        """Create user - NO AUTH CHECK (should be flagged)."""
        # VULNERABILITY: Password stored in plaintext (should be flagged)
        user = User(
            username=input.username,
            email=input.email,
            password=input.password  # Should be hashed!
        )
        user.save()
        return user

    def resolve_update_user(self, info, id, input):
        """Update user - NO AUTH CHECK (should be flagged)."""
        user = User.objects.get(id=id)
        if input.username:
            user.username = input.username
        if input.email:
            user.email = input.email
        user.save()
        return user

    def resolve_delete_user(self, info, id):
        """Delete user - NO AUTH CHECK (should be flagged)."""
        User.objects.filter(id=id).delete()
        return True

    def resolve_create_post(self, info, input):
        """Create post - NO AUTH CHECK (should be flagged)."""
        post = Post(
            title=input.title,
            content=input.content,
            author_id=input.author_id
        )
        post.save()
        return post


schema = graphene.Schema(query=Query, mutation=Mutation)
