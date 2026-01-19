def process(data, flag1, flag2, flag3, mode, option):
    # BUG: Too many parameters, high cyclomatic complexity
    if flag1:
        if flag2:
            if flag3:
                if mode == "a":
                    if option:
                        return data.upper()
                    else:
                        return data.lower()
                elif mode == "b":
                    return data.strip()
            else:
                return data
        else:
            return None
    return ""
