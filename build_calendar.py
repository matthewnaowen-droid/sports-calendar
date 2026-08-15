import datetime
import requests
from ics import Calendar, Event
import pytz

# ==========================================
# CONFIGURATION & DATA MAPPINGS
# ==========================================

FOLLOWED_TEAMS = [
    "Liverpool",
    "Auckland FC",
    "New Zealand Warriors",
    "Sydney Roosters",
    "New Zealand",  # All Blacks / Black Caps
]

# Regional TV Rights Mapping Engine
BROADCAST_RIGHTS = {
    "Liverpool": {
        "UK": "Sky Sports / TNT Sports / Amazon Prime / BBC",
        "NZ": "Sky Sport NOW / Sky Sport 1"
    },
    "Auckland FC": {
        "UK": "TNT Sports / Sky Sports",
        "NZ": "Sky Sport 1 / Sky Sport NOW"
    },
    "New Zealand Warriors": {
        "UK": "Sky Sports Action / Arena",
        "NZ": "Sky Sport 4 / Sky Sport NOW"
    },
    "Sydney Roosters": {
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
    "Default Marquee": {
        "UK": "Sky Sports / TNT Sports / BBC",
        "NZ": "Sky Sport / TVNZ+"
    }
}

# TheSportsDB API Base Setup
BASE_URL = "https://www.thesportsdb.com/api/v1/json/3/eventsnext.php?id="

# TheSportsDB Team IDs
TEAM_IDS = {
    "Liverpool": "133602",
    "Auckland FC": "141284",
    "New Zealand Warriors": "135182",
    "Sydney Roosters": "135180",
    "All Blacks": "135185",
    "Black Caps": "135186"
}

def get_broadcast_info(team_name):
    """Resolve UK and NZ broadcast information for a given team."""
    for key, rights in BROADCAST_RIGHTS.items():
        if key.lower() in team_name.lower():
            return rights
    return BROADCAST_RIGHTS["Default Marquee"]

def fetch_team_fixtures():
    """Fetch next fixtures for followed teams with robust key handling."""
    events = []
    
    for team, team_id in TEAM_IDS.items():
        url = f"{BASE_URL}{team_id}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200 and res.json().get('events'):
                for ev in res.json()['events']:
                    # Robust key lookup for API date/time variations
                    event_date = ev.get('strDate') or ev.get('dateEvent')
                    event_time = ev.get('strTime') or '00:00:00'
                    
                    if not event_date:
                        continue

                    if len(event_time) == 5:
                        event_time += ":00"

                    events.append({
                        'summary': f"🔴 {ev.get('strEvent', team)}",
                        'start': f"{event_date}T{event_time}Z",
                        'home': ev.get('strHomeTeam', ''),
                        'away': ev.get('strAwayTeam', ''),
                        'league': ev.get('strLeague', 'Sports Event'),
                        'venue': ev.get('strVenue', 'TBC'),
                        'team_key': team,
                        'is_marquee': False
                    })
        except Exception as e:
            print(f"Skipping {team} due to fetch error: {e}")
            
    return events

def fetch_marquee_discoveries(existing_events, cap=3):
    """
    Surprise/Serendipity Engine:
    Select up to `cap` major neutral derbies/finals per week.
    """
    marquee_candidates = [
        {
            'summary': "⭐ [Marquee] Real Madrid vs Barcelona",
            'start': "2026-10-25T19:00:00Z",
            'league': "La Liga",
            'venue': "Santiago Bernabéu",
            'team_key': "Default Marquee",
            'is_marquee': True
        }
    ]
    return marquee_candidates[:cap]

def build_ical_feed():
    """Build and write out the .ics calendar file."""
    cal = Calendar()
    
    # 1. Fetch Explicit Team Fixtures
    fixtures = fetch_team_fixtures()
    
    # 2. Inject Marquee Events (Capped)
    fixtures.extend(fetch_marquee_discoveries(fixtures, cap=3))
    
    for item in fixtures:
        event = Event()
        event.name = item['summary']
        
        # Parse UTC time
        try:
            dt = datetime.datetime.strptime(item['start'], "%Y-%m-%dT%H:%M:%SZ")
            event.begin = pytz.utc.localize(dt)
            event.duration = datetime.timedelta(hours=2)
        except ValueError:
            continue

        # Get viewing channels
        tv_info = get_broadcast_info(item['team_key'])
        
        # Populate Details & Metadata
        event.location = f"UK: {tv_info['UK']} | NZ: {tv_info['NZ']}"
        event.description = (
            f"🏆 Competition: {item['league']}\n"
            f"📍 Venue: {item['venue']}\n\n"
            f"📺 WHERE TO WATCH:\n"
            f"• 🇬🇧 UK: {tv_info['UK']}\n"
            f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
            f"🔄 Automated update via My Sports Calendar Pipeline."
        )
        
        cal.events.add(event)
        
    with open('sports.ics', 'w', encoding='utf-8') as f:
        f.writelines(cal.serialize_iter())
        
    print(f"Successfully generated sports.ics with {len(cal.events)} events!")

if __name__ == "__main__":
    build_ical_feed()
