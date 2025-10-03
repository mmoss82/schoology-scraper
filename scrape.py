"""
Schoology Calendar Summary Emailer
----------------------------------

Author: Matt Moss (@mattmoss82)
License: MIT
Created: 2025-10-03
Version: 1.0.0
"""

import requests
import os
import sys
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import html
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
import json
import argparse

load_dotenv()

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
SCHOOLOGY_USER = os.getenv('SCHOOLOGY_USER')
SCHOOLOGY_PASS = os.getenv('SCHOOLOGY_PASS')
CHILDREN = json.loads(os.getenv('CHILDREN', '[]'))
EMAIL_TO = json.loads(os.getenv('EMAIL_TO', '[]'))

URL='https://app.schoology.com'
SESSION = requests.Session()


def get_tomorrow_range():
    tomorrow = datetime.now() + timedelta(days=1)
    start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())

def parse_args():
    parser = argparse.ArgumentParser(description="Schoology summary emailer")
    parser.add_argument('--mode', choices=['weekly', 'tomorrow'], default='weekly',
                        help='Choose summary mode: weekly or tomorrow')
    return parser.parse_args()


def login():

    LOGIN_URL = f'{URL}/login'
    HOME_URL = f'{URL}/parent/home'
    payload = {
        'mail': SCHOOLOGY_USER,
        'pass': SCHOOLOGY_PASS,
        'school': '',
        'school_nid': '',
        'form_build_id': 'df73410-5f4QyA7ldmjQ0xjznEmKINTNl77pSQfm_z0fBVi2idI',
        'form_id': 's_user_login_form'
    }

    login_response = SESSION.post(LOGIN_URL, data=payload, allow_redirects=True)

    if login_response.ok:
        print("Login successful")
        print(SESSION.cookies.get_dict())

def switch_child(child_data):
    child_name = child_data['name']
    child_id = child_data['id']
    response = SESSION.get(f'{URL}/parent/switch_child/{child_id}')
    if response.ok:
        print(f'Switched child to: {child_name}')

def get_this_week_range():
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)          # Sunday

    start_ts = int(start_of_week.timestamp())
    end_ts = int(end_of_week.timestamp())

    return start_ts, end_ts

def get_next_week_range():
    today = datetime.now()
    start_of_next_week = today + timedelta(days=(7 - today.weekday()))
    end_of_next_week = start_of_next_week + timedelta(days=6)

    start_ts = int(start_of_next_week.timestamp())
    end_ts = int(end_of_next_week.timestamp())

    return start_ts, end_ts

def get_calendar(start, end):
    r = SESSION.get(f'{URL}/parent/calendar?ajax=1&start={start}&end={end}')

    parsed = []
    for item in r.json():
        title = html.unescape(item.get('titleText', ''))
        start = html.unescape(item.get('start'))
        course = html.unescape(item.get('content_title'))
        body_html = item.get('body', '')
        body_text = html.unescape(BeautifulSoup(body_html, 'html.parser').get_text(separator='\n').strip())
        event_type = item.get('e_type')

        parsed.append({
            'title': title,
            'start': datetime.strptime(start, '%Y-%m-%d %H:%M:%S'),
            'course': course,
            'type': event_type,
            'description': body_text
        })

    return parsed


def format_multi_child_summary(child_summaries):
    header = ["📅 **Weekly Schoology Summary**\n"]
    details = ["\n📝 **Full Assignment Details**\n"]

    for child_name, events in child_summaries.items():
        header.append(f"\n👤 **{child_name}**")
        for e in sorted(events, key=lambda x: x['start']):
            header.append(f"• {e['start'].strftime('%a %b %d')} — {e['title']}")

        details.append(f"\n👤 **{child_name}**")
        for e in sorted(events, key=lambda x: x['start']):
            date_str = e['start'].strftime('%A, %b %d at %I:%M %p')
            details.append(f"\n📌 {date_str}\n*{e['course']}*: **{e['title']}**")
            if e['description']:
                details.append(f"  ↪ {e['description']}")

    return "\n".join(header + details)

def send_email(body, email):
    msg = MIMEText(body)
    msg['Subject'] = f'Weekly Schoology Summary'
    msg['From'] = EMAIL_USER
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)


def main():
    args = parse_args()
    login()

    child_summaries = {}

    for child in CHILDREN:
        switch_child(child)
        child_name = child['name']

        if args.mode == 'weekly':
            start, end = get_next_week_range()
        else:
            start, end = get_tomorrow_range()

        events = get_calendar(start, end)
        child_summaries[child_name] = events

    summary = format_multi_child_summary(child_summaries)

    # Preview or send
    if os.getenv('PREVIEW_ONLY') == 'true':
        print(summary)
    else:
        for email in EMAIL_TO:
            send_email(summary, email)


if __name__ == '__main__':
    main()
