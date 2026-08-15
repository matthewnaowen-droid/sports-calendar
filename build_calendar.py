import datetime
import requests
from ics import Calendar, Event
import pytz

# ==========================================
# DYNAMIC TEAMS & LEAGUES CONFIGURATION
# ==========================================

# Teams to track dynamically
TRACKED_TEAMS = [
    "Liverpool",
    "Auckland FC",
    "New Zealand Warriors",
    "Warriors",
    "Sydney Roosters",
    "Roosters",
    "All Blacks",
    "New Zealand",
    "Black Caps"
]

# ESPN Public API Endpoints (Soccer & Rugby League/Union)
ENDPOINTS = [
    # English Premier League
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
    # Australian A-League Men
    "https://site.api.espn.com/apis/site/v2/sports/soccer/aus.1/scoreboard",
    # NRL (National Rugby League)
    "https://site.api.espn.com/apis/site/v2/sports/rugby/league/scoreboard",
    # International Rugby Union
    "https://site.api.espn.com/apis/site/v2/sports/rugby/union/scoreboard"
]

# Regional TV Rights Lookup
BROADCAST_RIGHTS = {
    "Liverpool": {"UK": "Sky Sports / TNT Sports / Amazon Prime", "NZ": "Sky Sport NOW / Sky Sport 1"},
    "Auckland FC": {"UK": "TNT Sports / Sky Sports", "NZ": "Sky Sport 1 / Sky Sport NOW"},
    "Warriors": {"UK": "Sky Sports Action / Arena", "NZ": "Sky Sport 4 / Sky Sport NOW"},
    "Roosters": {"UK": "Sky Sports Action / Arena", "NZ": "Sky Sport 4 / Sky Sport NOW"},
    "All Blacks": {"UK": "Sky Sports / TNT Sports", "NZ": "Sky Sport 1 / Sky Sport NOW"},
    "Black Caps": {"UK": "TNT Sports / Sky Sports", "NZ": "TVNZ 1 / TVNZ+ / Sky Sport"},
    "Default": {"UK": "Sky Sports / TNT Sports", "NZ": "Sky Sport NOW"}
}

def get_tv_rights(team_name):
    for key, rights in BROADCAST_RIGHTS.items():
        if key.lower() in team_name.lower():
            return rights
    return BROADCAST_RIGHTS["Default"]

def fetch_dynamic_fixtures():
    events = []
    
    for url in ENDPOINTS:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                continue
            
            data = res.json()
            for ev in data.get('events', []):
                name = ev.get('name', '')
                
                # Check if any tracked team is playing in this match
                matched_team = None
                for team in TRACKED_TEAMS:
                    if team.lower() in name.lower():
                        matched_team = team
                        break
                
                if matched_team:
                    # Extract date and venue
                    date_str = ev.get('date') # ISO format: YYYY-MM-DDTHH:MMZ
                    competitions = ev.get('competitions', [{}])[0]
                    venue = competitions.get('venue', {}).get('fullName', 'TBC')
                    league_name = data.get('leagues', [{}])[0].get('name', 'Sports Event')
                    
                    if date_str:
                        events.append({
                            'summary': f"🔴 {name}",
                            'start': date_str,
                            'league': league_name,
                            'venue': venue,
                            'team_key': matched_team
                        })
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
            
    return events

def build_ical_feed():
    cal = Calendar()
    fixtures = fetch_dynamic_fixtures()
    
    for item in fixtures:
        event = Event()
        event.name = item['summary']
        
        try:
            # Parse ISO timestamp from ESPN
            clean_date = item['start'].replace('Z', '+00:00')
            dt = datetime.datetime.fromisoformat(clean_date)
            event.begin = dt
            event.duration = datetime.timedelta(hours=2)
        except Exception:
            continue

        tv_info = get_tv_rights(item['team_key'])
        event.location = f"UK: {tv_info['UK']} | NZ: {tv_info['NZ']}"
        event.description = (
            f"🏆 Competition: {item['league']}\n"
            f"📍 Venue: {item['venue']}\n\n"
            f"📺 WHERE TO WATCH:\n"
            f"• 🇬🇧 UK: {tv_info['UK']}\n"
            f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
            f"🔄 Automated dynamic sync via My Sports Calendar Pipeline."
        )
        cal.events.add(event)
        
    with open('sports.ics', 'w', encoding='utf-8') as f:
        f.writelines(cal.serialize_iter())
        
    print(f"Successfully generated dynamic sports.ics with {len(cal.events)} live events!")

if __name__ == "__main__":
    build_ical_feed()
