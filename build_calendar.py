import requests
from ics import Calendar, Event
import datetime
import pytz

# ==========================================
# CONFIGURATION & SOURCE ICS FEEDS
# ==========================================

# Followed teams list
TARGET_TEAMS = [
    "Liverpool",
    "Auckland FC",
    "Warriors",
    "Roosters",
    "All Blacks",
    "Black Caps"
]

# Reliable source ICS feeds
SOURCE_FEEDS = [
    # Liverpool (Football Web Pages Feed)
    "https://www.footballwebpages.co.uk/liverpool/calendar.ics",
    # Reddit LFC Maintained Feed Backup
    "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
]

# Custom UK and NZ Broadcast Mapping Rules
BROADCAST_RIGHTS = {
    "Liverpool": {
        "UK": "Sky Sports / TNT Sports / Amazon Prime / BBC",
        "NZ": "Sky Sport NOW / Sky Sport 1"
    },
    "Auckland FC": {
        "UK": "TNT Sports / Sky Sports",
        "NZ": "Sky Sport 1 / Sky Sport NOW"
    },
    "Warriors": {
        "UK": "Sky Sports Action / Arena",
        "NZ": "Sky Sport 4 / Sky Sport NOW"
    },
    "Roosters": {
        "UK": "Sky Sports Action / Arena",
        "NZ": "Sky Sport 4 / Sky Sport NOW"
    },
    "All Blacks": {
        "UK": "Sky Sports / TNT Sports",
        "NZ": "Sky Sport 1 / Sky Sport NOW"
    },
    "Black Caps": {
        "UK": "TNT Sports / Sky Sports",
        "NZ": "TVNZ 1 / TVNZ+ / Sky Sport"
    },
    "Default": {
        "UK": "Sky Sports / TNT Sports",
        "NZ": "Sky Sport NOW"
    }
}

def get_broadcast_info(title):
    """Determine UK/NZ broadcast rights based on match title."""
    for team, rights in BROADCAST_RIGHTS.items():
        if team.lower() in title.lower():
            return rights
    return BROADCAST_RIGHTS["Default"]

def build_aggregated_calendar():
    out_calendar = Calendar()
    seen_events = set()

    for url in SOURCE_FEEDS:
        try:
            res = requests.get(url, timeout=15)
            if res.status_code != 200:
                print(f"Skipping feed (Status {res.status_code}): {url}")
                continue

            in_calendar = Calendar(res.text)
            
            for event in in_calendar.events:
                title = event.name or ""
                
                # Verify if this match involves one of your tracked teams
                matched_team = None
                for team in TARGET_TEAMS:
                    if team.lower() in title.lower():
                        matched_team = team
                        break
                        
                if matched_team or "Liverpool" in url:
                    # Deduplicate by start date and title
                    event_key = f"{event.begin.strftime('%Y-%m-%d-%H:%M')}-{title}"
                    if event_key in seen_events:
                        continue
                    seen_events.add(event_key)

                    # Create enriched event object
                    tv_info = get_broadcast_info(title)
                    new_event = Event()
                    new_event.name = f"🔴 {title}" if not title.startswith("🔴") else title
                    new_event.begin = event.begin
                    new_event.duration = event.duration or datetime.timedelta(hours=2)
                    new_event.location = f"UK: {tv_info['UK']} | NZ: {tv_info['NZ']}"
                    
                    venue = event.location or "TBC"
                    new_event.description = (
                        f"📍 Location / Venue: {venue}\n\n"
                        f"📺 WHERE TO WATCH:\n"
                        f"• 🇬🇧 UK: {tv_info['UK']}\n"
                        f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
                        f"🔄 Auto-synced via My Sports Calendar Pipeline."
                    )

                    out_calendar.events.add(new_event)

        except Exception as e:
            print(f"Error processing feed {url}: {e}")

    with open("sports.ics", "w", encoding="utf-8") as f:
        f.writelines(out_calendar.serialize_iter())

    print(f"Successfully generated sports.ics with {len(out_calendar.events)} total events!")

if __name__ == "__main__":
    build_aggregated_calendar()
