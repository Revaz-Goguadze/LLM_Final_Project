def get_users_with_posts(user_ids):
    results = []
    for user_id in user_ids:
        user = db.query("SELECT * FROM users WHERE id = ?", user_id)
        posts = db.query("SELECT * FROM posts WHERE user_id = ?", user_id)
        user["posts"] = posts
        results.append(user)
    return results
