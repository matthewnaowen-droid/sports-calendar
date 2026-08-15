import requests
from icalendar import Calendar, Event
import datetime
import pytz
import uuid

# Verified working endpoints from terminal audit
SOURCE_FEEDS = [
    # Liverpool (19 KB)
    "https://www.footballwebpages.co.uk/liverpool/calendar.ics",
    # NRL Complete Feed - Warriors & Roosters (630 KB)
    "https://calendar.google.com/calendar/ical/p520al5mfgqq5m2a8pu021nv0c%40group.calendar.google.com/public/basic.ics"
]

TARGET_TEAMS = [
    "Liverpool",
    "Warriors",
    "Roosters",
    "Auckland FC",
    "All Blacks",
    "Black Caps"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def resolve_broadcast_channels(team, dtstart):
    """Determine broadcast details without generic channel dumps."""
    if team in ["Liverpool", "Auckland FC"]:
        if isinstance(dtstart, datetime.datetime):
            dt_utc = dtstart.astimezone(pytz.utc) if dtstart.tzinfo else pytz.utc.localize(dtstart)
            # Saturday 12:30 BST -> TNT Sports 1
            if dt_utc.weekday() == 5 and dt_utc.hour in [11, 12]:
                return {"UK": "TNT Sports 1", "NZ": "Sky Sport NOW / Sky Sport 1"}
            # Sunday 16:30 BST -> Sky Sports Main Event
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
    parsed_counts = {team: 0 for team in TARGET_TEAMS}

    for url in SOURCE_FEEDS:
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                print(f"Skipping feed ({res.status_code}): {url}")
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
                            
                    # Process matching team or Liverpool feed
                    if matched_team or "liverpool" in url.lower():
                        active_team = matched_team if matched_team else "Liverpool"
                        dtstart = component.get('dtstart')
                        if not dtstart:
                            continue
                        
                        start_time = dtstart.dt
                        time_str = start_time.strftime('%Y-%m-%d-%H:%M') if isinstance(start_time, datetime.datetime) else str(start_time)
                        
                        # Deduplication key: timestamp + active team keyword
                        dedup_key = f"{time_str}_{active_team.lower()}"
                        
                        if dedup_key in seen_event_keys:
                            continue
                        seen_event_keys.add(dedup_key)

                        tv_info = resolve_broadcast_channels(active_team, start_time)
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
                        
                        # Venue in location field only
                        venue = str(component.get('location', 'TBC'))
                        new_event.add('location', venue)
                        
                        # Clean description
                        description_str = (
                            f"📺 WHERE TO WATCH:\n"
                            f"• 🇬🇧 UK: {tv_info['UK']}\n"
                            f"• 🇳🇿 NZ: {tv_info['NZ']}\n\n"
                            f"🔄 Auto-synced via My Sports Calendar Pipeline."
                        )
                        new_event.add('description', description_str)

                        out_calendar.add_component(new_event)
                        parsed_counts[active_team] += 1

        except Exception as e:
            print(f"Error processing feed {url}: {e}")

    with open("sports.ics", "wb") as f:
        f.write(out_calendar.to_ical())

    print("\n--- Event Parse Summary ---")
    for team, count in parsed_counts.items():
        print(f"• {team}: {count} events")
    print(f"Total Unique Events Saved: {len(seen_event_keys)}")

if __name__ == "__main__":
    build_aggregated_calendar()
