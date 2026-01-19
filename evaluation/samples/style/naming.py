def calc(x, y, z):
    # BUG: Non-descriptive function and parameter names
    return x * y + z


def ProcessData(Data):
    # BUG: PascalCase for function (should be snake_case)
    return Data.strip()


class userManager:
    # BUG: Class should be PascalCase
    def GetUser(self, ID):
        # BUG: Method should be snake_case
        pass
