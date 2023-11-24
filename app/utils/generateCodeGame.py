import random
import string

def generate_game_code():
    return ''.join(random.choices(string.ascii_uppercase, k=6))