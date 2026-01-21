def get_user_email(user):
    return user.email.lower()


def process_config(config):
    timeout = config["settings"]["timeout"]
    return timeout * 1000


def get_first_item(items):
    return items[0]
