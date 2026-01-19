def get_user_email(user):
    # BUG: No null check - AttributeError if user is None
    return user.email.lower()


def process_config(config):
    # BUG: KeyError if 'settings' missing
    timeout = config["settings"]["timeout"]
    return timeout * 1000


def get_first_item(items):
    # BUG: IndexError on empty list
    return items[0]
