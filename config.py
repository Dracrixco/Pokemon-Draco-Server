"""
Configuration settings for the Pokemon Cable Club Server.
This file contains all the server configuration constants and settings.
"""

# Server Configuration
HOST = r"0.0.0.0"
PORT = 9999
API_PORT = 8080

# Directory Configuration
PBS_DIR = r"./PBS"
LOG_DIR = r"."
RULES_DIR = "./OnlinePresets"

# Timing Configuration
RULES_REFRESH_RATE = 60  # Approximately in seconds

# Game Limits and Constraints
POKEMON_MAX_NAME_SIZE = 10
PLAYER_MAX_NAME_SIZE = 10
MAXIMUM_LEVEL = 100
IV_STAT_LIMIT = 31
EV_LIMIT = 510
EV_STAT_LIMIT = 252

# Special Move IDs
SKETCH_MOVE_IDS = ["SKETCH"]  # Moves that permanently copy other moves

# Plugin Configuration - Essentials Deluxe Plugins
ESSENTIALS_DELUXE_INSTALLED = False  # Specifically Essentials Deluxe, not DBK
MUI_MEMENTOS_INSTALLED = False
ZUD_DYNAMAX_INSTALLED = False  # ZUD Mechanics / [DBK] Dynamax
PLA_INSTALLED = False  # PLA Battle Styles
TERA_INSTALLED = False  # Terastal Phenomenon / [DBK] Terastallization
FOCUS_INSTALLED = False  # Focus Meter System