import re

def is_valid_domain(domain: str) -> bool:
    pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.(?:[A-Za-z]{2,})$"
    return re.match(pattern, domain) is not None 