"""Run a selected native Windows check; default: one-account world smoke test."""
import argparse
import subprocess
import sys
from pathlib import Path

SUITES = {
    "chat-layout": ("verify_chat.py", ["--layout"]),
    "chat-history": ("verify_chat.py", ["--history"]),
    "chat-bubbles": ("verify_chat.py", ["--bubbles"]),
    "chat": ("verify_chat.py", []),
    "ui-regressions": ("verify_ui_regressions.py", []),
    "room-audio": ("verify_room_audio.py", []),
    "minigames": ("verify_minigames.py", []),
    "login-outfits": ("verify_login_outfits.py", []),
    "admin-catalog": ("verify_shops.py", ["--catalog"]),
    "commands": ("verify_multiplayer.py", ["--commands"]),
    "wardrobe": ("verify_multiplayer.py", ["--wardrobe"]),
    "shops": ("verify_shops.py", []),
    "world-shops": ("verify_shops.py", ["--world-points"]),
    "admin": ("verify_admin.py", []),
    "shop-admin": ("verify_admin.py", []),  # Previous suite name.
    "room-links": ("verify_multiplayer.py", ["--room-links"]),
    "map-timing": ("verify_multiplayer.py", ["--map-timing"]),
    "map-ui": ("verify_multiplayer.py", ["--map-ui"]),
    "rooms": ("verify_multiplayer.py", ["--rooms"]),
    "rooms-all": ("verify_multiplayer.py", ["--rooms-all"]),
    "layout": ("verify_multiplayer.py", ["--layout"]),
    "spawns": ("verify_world.py", ["--spawns"]),
    "world": ("verify_world.py", []),
    "presence": ("verify_multiplayer.py", ["--presence"]),
    "friends-ui": ("verify_multiplayer.py", ["--friends-ui"]),
    "friends": ("verify_multiplayer.py", ["--friends-only"]),
    "social": ("verify_multiplayer.py", ["--social"]),
    "profiles": ("verify_multiplayer.py", ["--profiles"]),
    "multiplayer": ("verify_multiplayer.py", []),
    "registration": ("verify_desktop.py", []),
    "accounts": ("verify_saved_mogobes.py", ["--full"]),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="world",
                        help="world: one account; presence: online players and server friend icon; social: emotions, magic, friends and mute; profiles: two original profile cards and counters; multiplayer: two players and duplicate login; registration: complete registration; accounts: six saved accounts; all: explicit full run")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    for suite in SUITES if args.suite == "all" else [args.suite]:
        script, arguments = SUITES[suite]
        print(f"Running native suite: {suite}", flush=True)
        completed = subprocess.run([sys.executable, str(directory/script), *arguments])
        if completed.returncode:
            raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
