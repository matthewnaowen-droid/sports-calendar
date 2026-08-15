import requests
from icalendar import Calendar, Event
import datetime
import pytz
import uuid

# Configuration: Tracked teams and their respective dedicated source feeds
TEAM_FEEDS = {
    "Liverpool": [
        "https://www.footballwebpages.co.uk/liverpool/calendar.ics"
    ],
    "Warriors": [
        "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
    ],
    "Roosters": [
        "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
    ],
    "Auckland FC": [
        "https://www.footballwebpages.co.uk/auckland-fc/calendar.ics"
    ],
    "All Blacks": [
        "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
    ],
    "Black Caps": [
        "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
    ]
}

# Broadcast lookup logic based on team and kickoff times
def resolve_broadcast_channels(team, dtstart):
    """Determine precise broadcast rights without dumping generic channel lists."""
    if team == "Liverpool" or team == "Auckland FC":
        if isinstance(dtstart, datetime.datetime):
            # 12:30 BST Saturday slot -> TNT Sports in UK
            if dtstart.weekday() == 5 and dtstart.hour == 11:
                return {"UK": "TNT Sports 1", "NZ": "Sky Sport NOW / Sky Sport 1"}
            # 16:30 BST Sunday slot -> Sky Sports in UK
            elif dtstart.weekday() == 6 and dtstart.hour == 15:
                return {"UK": "Sky Sports Main Event", "NZ": "Sky Sport NOW / Sky Sport 1"}
        return {"UK": "Sky Sports / TNT Sports", "NZ": "Sky Sport NOW / Sky Sport 1"}
        
    elif team in ["Warriors", "Roosters"]:
        return {"UK": "Sky Sports Action / Arena", "NZ": "Sky Sport 4 / Sky Sport NOW"}
        
    elif team == "All Blacks":
        return {"UK": "Sky Sports Action", "NZ": "Sky Sport 1 / Sky Sport NOW"}
        
    elif team == "Black Caps":
        return {"UK": "TNT Sports", "NZ": "TVNZ 1 / Sky Sport"}
        
    return {"UK": "Sky Sports / TNT Sports", "NZ": "Sky Sport NOW"}

def build_aggregated_calendar():
    out_calendar = Calendar()
    out_calendar.add('prodid', '-//My Sports Calendar Pipeline//EN')
    out_calendar.add('version', '2.0')

    seen_event_keys = set()
    now_utc = datetime.datetime.now(pytz.utc)

    for team, feeds in TEAM_FEEDS.items():
        for url in feeds:
            try:
                res = requests.get(url, timeout=15)
                if res.status_code != 200:
                    continue

                in_calendar = Calendar.from_ical(res.text)
                
                for component in in_calendar.walk():
                    if component.name == "VEVENT":
                        title = str(component.get('summary', ''))
                        
                        # Match team keyword in event title
                        if team.lower() in title.lower() or (team == "Liverpool" and "footballwebpages" in url):
                            dtstart = component.get('dtstart')
                            if not dtstart:
                                continue
                            
                            start_time = dtstart.dt
                            
                            # Team-aware deduplication key: timestamp + team_name
                            time_str = start_time.strftime('%Y-%m-%d-%H:%M') if isinstance(start_time, datetime.datetime) else str(start_time)
                            dedup_key = f"{time_str}_{team.lower()}"
                            
                            if dedup_key in seen_event_keys:
                                continue
                            seen_event_keys.add(dedup_key)

                            tv_info = resolve_broadcast_channels(team, start_time)
                            new_event = Event()
                            
                            summary_text = f"🔴 {title}" if not title.startswith("🔴") else title
                            new_event.add('summary', summary_text)
                            new_event.add('dtstart', start_time)
                            
                            dtend = component.get('dtend')
                            if dtend:
                                new_event.add('dtend', dtend.dt)
                            else:
                                if isinstance(start_time, datetime.datetime):
                                    new_event.add('dtend', start_time + datetime.timedelta(hours=2))
                                else:
                                    new_event.add('dtend', start_time + datetime.timedelta(days=1))
                                
                            new_event.add('dtstamp', now_utc)
                            new_event.add('uid', f"{uuid.uuid4()}@mysportscalendar")
                            
                            # Clean Location field: Stadium / Venue only
                            venue = str(component.get('location', 'TBC'))
                            new_event.add('location', venue)
                            
                            # Clean Description field: Structured broadcast info
                            description_str = (
                                f"📍 Venue: {venue}\n\n"
                                f"📺 WHERE TO WATCH:\n"
                                f"• 🇬🇧 UK: {tv_info['UK']}\n"
                                f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
                                f"🔄 Auto-synced via My Sports Calendar Pipeline."
                            )
                            new_event.add('description', description_str)

                            out_calendar.add_component(new_event)

            except Exception as e:
                print(f"Error processing feed {url}: {e}")

    with open("sports.ics", "wb") as f:
        f.write(out_calendar.to_ical())

    print("Successfully generated clean, multi-team sports.ics feed!")

if __name__ == "__main__":
    build_aggregated_calendar()
