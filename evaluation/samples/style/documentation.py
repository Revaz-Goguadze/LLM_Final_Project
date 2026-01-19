def x(a, b, c):
    # BUG: No docstring, cryptic names
    return (a + b) * c if c else 0


class DataProcessor:
    # BUG: No class docstring
    def run(self, input):
        # BUG: 'input' shadows builtin
        pass

    def _internal(self):
        # Missing docstring for complex private method
        pass
