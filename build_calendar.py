import os
import json
import re
import urllib.request
import datetime
import uuid
from icalendar import Calendar, Event
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def clean_title(title):
    if not title:
        return "Match"
    # Remove emojis and non-standard text symbols
    cleaned = re.sub(r'[^\w\s\-\.\,\&\(\)\/]', '', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Standardise match separators (v, V, -, –) to clean 'vs'
    cleaned = re.sub(r'\s+(?:v|vs|V|Vs|–|-)\s+', ' vs ', cleaned)
    return cleaned

def get_broadcast_info(title, calendar_name=""):
    combined = f"{title} {calendar_name}".lower()
    
    if 'liverpool' in combined:
        return {'UK': 'TNT Sports / Sky Sports', 'NZ': 'Sky Sport NOW / Sky Sport 1'}
    elif any(k in combined for k in ['warriors', 'roosters', 'rabbitohs', 'nrl']):
        return {'UK': 'Sky Sports Mix / Action', 'NZ': 'Sky Sport NOW / Sky Sport 1'}
    elif any(k in combined for k in ['all blacks', 'rugby']):
        return {'UK': 'TNT Sports / Sky Sports', 'NZ': 'Sky Sport NOW / Sky Sport 1'}
    elif any(k in combined for k in ['black caps', 'cricket']):
        return {'UK': 'TNT Sports', 'NZ': 'Sky Sport NOW / Sky Sport 1'}
    else:
        return {'UK': 'TBC', 'NZ': 'Sky Sport NOW / Sky Sport 1'}

def format_description(venue, broadcast_info):
    return (
        f"🏟️ : {venue}\n"
        f"📺 :\n"
        f" 🇬🇧 {broadcast_info['UK']}\n"
        f" 🇳🇿 {broadcast_info['NZ']}"
    )

def get_google_calendar_events():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    calendar_list = service.calendarList().list().execute()
    events_list = []

    for calendar in calendar_list.get('items', []):
        cal_id = calendar['id']
        cal_name = calendar.get('summary', '')
        
        events_result = service.events().list(
            calendarId=cal_id,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for item in events_result.get('items', []):
            raw_summary = item.get('summary', 'Match')
            venue = item.get('location', 'TBC') or 'TBC'
            
            start_raw = item['start'].get('dateTime', item['start'].get('date'))
            end_raw = item['end'].get('dateTime', item['end'].get('date'))
            
            try:
                if 'T' in start_raw:
                    start_dt = datetime.datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
                else:
                    start_dt = datetime.datetime.fromisoformat(start_raw + 'T00:00:00+00:00')
                
                if end_raw:
                    if 'T' in end_raw:
                        end_dt = datetime.datetime.fromisoformat(end_raw.replace('Z', '+00:00'))
                    else:
                        end_dt = datetime.datetime.fromisoformat(end_raw + 'T00:00:00+00:00')
                else:
                    end_dt = start_dt
            except Exception:
                continue

            clean_name = clean_title(raw_summary)
            broadcast = get_broadcast_info(clean_name, cal_name)
            
            events_list.append({
                'summary': clean_name,
                'description': format_description(venue, broadcast),
                'location': venue,
                'start': start_dt,
                'end': end_dt
            })
            
    return events_list

def fetch_liverpool_feed():
    try:
        url = 'https://www.footballwebpages.co.uk/liverpool/calendar.ics'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            ics_data = response.read()
        gcal = Calendar.from_ical(ics_data)
        events = []
        for component in gcal.walk('vevent'):
            raw_summary = str(component.get('summary', 'Liverpool Match'))
            venue = str(component.get('location', 'TBC')) if component.get('location') else 'TBC'
            
            start = component.get('dtstart').dt
            end = component.get('dtend').dt if component.get('dtend') else start
            
            if isinstance(start, datetime.date) and not isinstance(start, datetime.datetime):
                start = datetime.datetime(start.year, start.month, start.day, tzinfo=datetime.timezone.utc)
            if isinstance(end, datetime.date) and not isinstance(end, datetime.datetime):
                end = datetime.datetime(end.year, end.month, end.day, tzinfo=datetime.timezone.utc)
                
            clean_name = clean_title(raw_summary)
            broadcast = get_broadcast_info(clean_name, 'Liverpool')
            
            events.append({
                'summary': clean_name,
                'description': format_description(venue, broadcast),
                'location': venue,
                'start': start,
                'end': end
            })
        return events
    except Exception as e:
        print(f"Error fetching Liverpool feed: {e}")
        return []

def load_json_fixtures():
    if not os.path.exists('fixtures.json'):
        return []
    with open('fixtures.json', 'r') as f:
        fixtures = json.load(f)
    
    events = []
    for fix in fixtures:
        team = fix.get('team', 'Black Caps')
        raw_summary = fix.get('summary', 'Match')
        start_str = fix.get('start')
        end_str = fix.get('end')
        venue = fix.get('venue', 'TBC')
        
        start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_dt = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else start_dt
        
        full_title = f"{team} vs {raw_summary}" if " vs " not in raw_summary.lower() and " v " not in raw_summary.lower() else raw_summary
        clean_name = clean_title(full_title)
        broadcast = get_broadcast_info(clean_name, team)
        
        events.append({
            'summary': clean_name,
            'description': format_description(venue, broadcast),
            'location': venue,
            'start': start_dt,
            'end': end_dt
        })
    return events

def build_aggregated_calendar():
    cal = Calendar()
    cal.add('prodid', '-//Sports Calendar Sync//EN')
    cal.add('version', '2.0')
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    all_events = []
    
    try:
        print("Fetching Google Calendar subscriptions...")
        all_events.extend(get_google_calendar_events())
    except Exception as e:
        print(f"Google Calendar fetch skipped or failed: {e}")
        
    print("Loading static JSON fixtures...")
    all_events.extend(load_json_fixtures())
    
    print("Fetching Liverpool fixtures...")
    all_events.extend(fetch_liverpool_feed())
    
    seen_keys = set()
    count = 0
    
    for ev in all_events:
        event_key = (ev['summary'].lower(), ev['start'].isoformat())
        if event_key in seen_keys:
            continue
        seen_keys.add(event_key)
        
        event = Event()
        event.add('dtstamp', now_utc)
        event.add('uid', f"{uuid.uuid4()}@mysportscalendar")
        event.add('summary', ev['summary'])
        event.add('description', ev['description'])
        if ev['location']:
            event.add('location', ev['location'])
            
        start = ev['start']
        end = ev['end']
        
        if isinstance(start, datetime.date) and not isinstance(start, datetime.datetime):
            start = datetime.datetime(start.year, start.month, start.day, tzinfo=datetime.timezone.utc)
        if isinstance(end, datetime.date) and not isinstance(end, datetime.datetime):
            end = datetime.datetime(end.year, end.month, end.day, tzinfo=datetime.timezone.utc)
            
        event.add('dtstart', start)
        event.add('dtend', end)
        
        cal.add_component(event)
        count += 1
        
    with open('sports.ics', 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"\nSuccessfully generated standardised sports.ics with {count} total events!")

if __name__ == "__main__":
    build_aggregated_calendar()
