import requests
from icalendar import Calendar, Event
import datetime
import pytz
import uuid
from dateutil import parser

# Live Liverpool iCal Feed
LIVERPOOL_FEED = "https://www.footballwebpages.co.uk/liverpool/calendar.ics"

# TheSportsDB Team IDs (Free Open API Tier)
SPORTS_DB_TEAMS = {
    "Warriors": "135153",      # NZ Warriors (NRL)
    "Roosters": "135151",      # Sydney Roosters (NRL)
    "All Blacks": "135288",    # New Zealand All Blacks
    "Auckland FC": "140683",   # Auckland FC (A-League)
    "Black Caps": "135606"     # NZ Cricket
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def resolve_broadcast_channels(team, dtstart):
    if team in ["Warriors", "Roosters"]:
        return {"UK": "Sky Sports Action / Arena", "NZ": "Sky Sport 4 / Sky Sport NOW"}
    elif team == "All Blacks":
        return {"UK": "Sky Sports Action", "NZ": "Sky Sport 1 / Sky Sport NOW"}
    elif team == "Black Caps":
        return {"UK": "TNT Sports", "NZ": "TVNZ 1 / Sky Sport"}
    elif team in ["Liverpool", "Auckland FC"]:
        if isinstance(dtstart, datetime.datetime):
            dt_utc = dtstart.astimezone(pytz.utc) if dtstart.tzinfo else pytz.utc.localize(dtstart)
            if dt_utc.weekday() == 5 and dt_utc.hour in [11, 12]:
                return {"UK": "TNT Sports 1", "NZ": "Sky Sport NOW / Sky Sport 1"}
            elif dt_utc.weekday() == 6 and dt_utc.hour in [15, 16]:
                return {"UK": "Sky Sports Main Event", "NZ": "Sky Sport NOW / Sky Sport 1"}
        return {"UK": "Sky Sports / TNT Sports", "NZ": "Sky Sport NOW / Sky Sport 1"}
    return {"UK": "Sky Sports / TNT Sports", "NZ": "Sky Sport NOW"}

def build_aggregated_calendar():
    out_calendar = Calendar()
    out_calendar.add('prodid', '-//My Sports Calendar Pipeline//EN')
    out_calendar.add('version', '2.0')

    seen_event_keys = set()
    now_utc = datetime.datetime.now(pytz.utc)
    parsed_counts = {"Liverpool": 0, "Warriors": 0, "Roosters": 0, "All Blacks": 0, "Auckland FC": 0, "Black Caps": 0}

    # 1. Parse Liverpool Live Feed
    try:
        res = requests.get(LIVERPOOL_FEED, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            in_calendar = Calendar.from_ical(res.text)
            for component in in_calendar.walk():
                if component.name == "VEVENT":
                    title = str(component.get('summary', ''))
                    dtstart = component.get('dtstart')
                    if not dtstart:
                        continue
                    
                    start_time = dtstart.dt
                    time_str = start_time.strftime('%Y-%m-%d-%H:%M') if isinstance(start_time, datetime.datetime) else str(start_time)
                    dedup_key = f"{time_str}_liverpool"
                    
                    if dedup_key in seen_event_keys:
                        continue
                    seen_event_keys.add(dedup_key)

                    tv_info = resolve_broadcast_channels("Liverpool", start_time)
                    new_event = Event()
                    
                    summary_text = f"🔴 {title}" if not title.startswith("🔴") else title
                    new_event.add('summary', summary_text)
                    new_event.add('dtstart', start_time)
                    
                    dtend = component.get('dtend')
                    if dtend:
                        new_event.add('dtend', dtend.dt)
                    else:
                        new_event.add('dtend', start_time + datetime.timedelta(hours=2) if isinstance(start_time, datetime.datetime) else start_time + datetime.timedelta(days=1))
                        
                    new_event.add('dtstamp', now_utc)
                    new_event.add('uid', f"{uuid.uuid4()}@mysportscalendar")
                    
                    venue = str(component.get('location', 'TBC'))
                    new_event.add('location', venue)
                    
                    description_str = (
                        f"📺 WHERE TO WATCH:\n"
                        f"• 🇬🇧 UK: {tv_info['UK']}\n"
                        f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
                        f"🔄 Auto-synced via My Sports Calendar Pipeline."
                    )
                    new_event.add('description', description_str)

                    out_calendar.add_component(new_event)
                    parsed_counts["Liverpool"] += 1
    except Exception as e:
        print(f"Error processing Liverpool feed: {e}")

    # 2. Fetch Multi-Sport Schedules via TheSportsDB API
    for team, team_id in SPORTS_DB_TEAMS.items():
        api_url = f"https://www.thesportsdb.com/api/v1/json/3/eventsnext.php?id={team_id}"
        try:
            res = requests.get(api_url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json()
                events = data.get("events") or []
                for evt in events:
                    event_title = evt.get("strEvent", f"{team} Match")
                    str_date = evt.get("strTimestamp") or f"{evt.get('dateEvent')}T{evt.get('strTime', '00:00:00')}"
                    
                    try:
                        start_time = parser.parse(str_date)
                        if not start_time.tzinfo:
                            start_time = pytz.utc.localize(start_time)
                    except Exception:
                        continue

                    time_str = start_time.strftime('%Y-%m-%d-%H:%M')
                    dedup_key = f"{time_str}_{team.lower()}"

                    if dedup_key in seen_event_keys:
                        continue
                    seen_event_keys.add(dedup_key)

                    tv_info = resolve_broadcast_channels(team, start_time)
                    new_event = Event()

                    icon = "🏉" if team in ["Warriors", "Roosters", "All Blacks"] else ("🏏" if team == "Black Caps" else "⚽")
                    new_event.add('summary', f"{icon} {event_title}")
                    new_event.add('dtstart', start_time)
                    new_event.add('dtend', start_time + datetime.timedelta(hours=2))
                    new_event.add('dtstamp', now_utc)
                    new_event.add('uid', f"{uuid.uuid4()}@mysportscalendar")
                    
                    venue = evt.get("strVenue") or "TBC"
                    new_event.add('location', venue)

                    description_str = (
                        f"📺 WHERE TO WATCH:\n"
                        f"• 🇬🇧 UK: {tv_info['UK']}\n"
                        f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
                        f"🔄 Auto-synced via My Sports Calendar Pipeline."
                    )
                    new_event.add('description', description_str)

                    out_calendar.add_component(new_event)
                    parsed_counts[team] += 1
        except Exception as e:
            print(f"Error fetching API data for {team}: {e}")

    with open("sports.ics", "wb") as f:
        f.write(out_calendar.to_ical())

    print("\n--- Verified API Parse Summary ---")
    for t, c in parsed_counts.items():
        print(f"• {t}: {c} events")

if __name__ == "__main__":
    build_aggregated_calendar()
