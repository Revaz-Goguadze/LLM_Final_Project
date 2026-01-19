cache = {}


def process_request(request_id, data):
    # BUG: Memory leak - cache grows unbounded
    cache[request_id] = data
    return analyze(data)


class EventHandler:
    handlers = []

    def register(self, callback):
        # BUG: Handlers never removed, memory leak
        self.handlers.append(callback)
