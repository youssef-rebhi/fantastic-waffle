import re


def sanitize_json_newlines(json_str):
    # Replace newlines inside string values with \\n
    def replacer(match):
        return match.group(0).replace('\n', '\\n')
    # This regex finds all quoted string values
    return re.sub(r'\"(.*?)\"', replacer, json_str, flags=re.DOTALL)
