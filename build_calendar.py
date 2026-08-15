import requests
from icalendar import Calendar, Event
import datetime
import pytz
import uuid

TARGET_TEAMS = [
    "Liverpool",
    "Auckland FC",
    "Warriors",
    "Roosters",
    "All Blacks",
    "Black Caps"
]

SOURCE_FEEDS = [
    "https://www.footballwebpages.co.uk/liverpool/calendar.ics",
    "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
]

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
    for team, rights in BROADCAST_RIGHTS.items():
        if team.lower() in title.lower():
            return rights
    return BROADCAST_RIGHTS["Default"]

def build_aggregated_calendar():
    out_calendar = Calendar()
    out_calendar.add('prodid', '-//My Sports Calendar Pipeline//EN')
    out_calendar.add('version', '2.0')

    seen_events = set()
    now_utc = datetime.datetime.now(pytz.utc)

    for url in SOURCE_FEEDS:
        try:
            res = requests.get(url, timeout=15)
            if res.status_code != 200:
                continue

            in_calendar = Calendar.from_ical(res.text)
            
            for component in in_calendar.walk():
                if component.name == "VEVENT":
                    title = str(component.get('summary', ''))
                    
                    matched_team = None
                    for team in TARGET_TEAMS:
                        if team.lower() in title.lower():
                            matched_team = team
                            break
                            
                    if matched_team or "Liverpool" in url:
                        dtstart = component.get('dtstart')
                        if not dtstart:
                            continue
                        
                        start_time = dtstart.dt
                        event_key = f"{start_time}-{title}"
                        if event_key in seen_events:
                            continue
                        seen_events.add(event_key)

                        tv_info = get_broadcast_info(title)
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
                        
                        location_str = f"UK: {tv_info['UK']} | NZ: {tv_info['NZ']}"
                        new_event.add('location', location_str)
                        
                        venue = str(component.get('location', 'TBC'))
                        description_str = (
                            f"📍 Location / Venue: {venue}\n\n"
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

    print("Successfully generated fully compliant RFC 5545 sports.ics!")

if __name__ == "__main__":
    build_aggregated_calendar()
