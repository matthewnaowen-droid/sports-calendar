import requests
from icalendar import Calendar, Event
import datetime
import pytz
import uuid

# Active, publicly accessible iCal source endpoints
TEAM_FEEDS = {
    "Liverpool": [
        "https://www.footballwebpages.co.uk/liverpool/calendar.ics"
    ],
    "Auckland FC": [
        "https://www.footballwebpages.co.uk/auckland-fc/calendar.ics"
    ],
    "Warriors": [
        "https://fixtur.es/en/ical/nr-new-zealand-warriors.ics"
    ],
    "Roosters": [
        "https://fixtur.es/en/ical/nr-sydney-roosters.ics"
    ],
    "All Blacks": [
        "https://fixtur.es/en/ical/team/new-zealand-rugby.ics"
    ],
    "Black Caps": [
        "https://fixtur.es/en/ical/team/new-zealand-cricket.ics"
    ]
}

def resolve_broadcast_channels(team, dtstart):
    """Determine precise broadcast rights without dumping generic channel lists."""
    if team in ["Liverpool", "Auckland FC"]:
        if isinstance(dtstart, datetime.datetime):
            # Ensure datetime is normalized to UTC
            dt_utc = dtstart.astimezone(pytz.utc) if dtstart.tzinfo else pytz.utc.localize(dtstart)
            # 11:30 UTC Saturday (12:30 BST) -> TNT Sports 1
            if dt_utc.weekday() == 5 and dt_utc.hour in [11, 12]:
                return {"UK": "TNT Sports 1", "NZ": "Sky Sport NOW / Sky Sport 1"}
            # 15:30 UTC Sunday (16:30 BST) -> Sky Sports Main Event
            elif dt_utc.weekday() == 6 and dt_utc.hour in [15, 16]:
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
                    print(f"Skipping feed {url} (Status {res.status_code})")
                    continue

                in_calendar = Calendar.from_ical(res.text)
                
                for component in in_calendar.walk():
                    if component.name == "VEVENT":
                        title = str(component.get('summary', ''))
                        
                        dtstart = component.get('dtstart')
                        if not dtstart:
                            continue
                        
                        start_time = dtstart.dt
                        
                        # Deduplicate by start date/time + team keyword
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
                        
                        # Set venue exclusively in location field
                        venue = str(component.get('location', 'TBC'))
                        new_event.add('location', venue)
                        
                        # Clean description without duplicating venue string
                        description_str = (
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
