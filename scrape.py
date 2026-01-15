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
from email.mime.multipart import MIMEMultipart
import json
import argparse
import logging

logger = logging.getLogger(__name__)
load_dotenv()

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
SCHOOLOGY_USER = os.getenv('SCHOOLOGY_USER')
SCHOOLOGY_PASS = os.getenv('SCHOOLOGY_PASS')
CHILDREN = json.loads(os.getenv('CHILDREN', '[]'))
EMAIL_TO = json.loads(os.getenv('EMAIL_TO', '[]'))
FORM_BUILD_ID = os.getenv('FORM_BUILD_ID')

URL='https://app.schoology.com'
SESSION = requests.Session()


def parse_args():
    parser = argparse.ArgumentParser(description="Schoology summary emailer")
    parser.add_argument('--mode', choices=['weekly', 'tomorrow', 'today'], default='weekly',
                        help='Choose summary mode: weekly, tomorrow, or today')
    return parser.parse_args()


def login():

    login_url = f'{URL}/login'
    payload = {
        'mail': SCHOOLOGY_USER,
        'pass': SCHOOLOGY_PASS,
        'school': '',
        'school_nid': '',
        'form_build_id': FORM_BUILD_ID,
        'form_id': 's_user_login_form'
    }

    login_response = SESSION.post(login_url, data=payload, allow_redirects=True)

    if login_response.ok:
        logger.info("Login successful")
    else:
        logger.error("Login failed")
        logger.error(login_response.text)

def switch_child(child_data):
    child_name = child_data['name']
    child_id = child_data['id']
    response = SESSION.get(f'{URL}/parent/switch_child/{child_id}')
    if response.ok:
        logger.info(f'Switched child to: {child_name}')
    else:
        logger.error(f'Unable to switch to: {child_name}')
        logger.error(response.text)

def get_day_range(offset):
    day = datetime.now() + timedelta(days=offset)
    start = datetime(day.year, day.month, day.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())

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

def fetch_schoology_tasks():
    """
    Scrapes the Schoology dashboard for upcoming and overdue items
    by parsing .date-header and .upcoming-event elements.

    Converts numeric 'start' values (epoch seconds strings) to datetime,
    and normalizes relative URLs to absolute URLs.
    """
    url = f"{URL}/parent/home"   # dashboard page
    html_doc = SESSION.get(url).text

    soup = BeautifulSoup(html_doc, "html.parser")

    results = {
        "overdue_submissions": [],
        "upcoming_events": [],
        "upcoming_submissions": []
    }

    # Find all date-header blocks (these define the category)
    for header in soup.select(".upcoming-list .date-header"):
        category = header.get("id")  # e.g. "overdue_submissions"
        if not category:
            continue

        # Walk forward through siblings until the next header
        el = header.find_next_sibling()
        while el and "upcoming-event" in el.get("class", []):
            # Extract fields
            title_el = el.select_one("a")
            course_el = el.select_one(".course-title")
            due_el = el.select_one(".due")

            raw_start = el.get("data-start")
            start_dt = None
            if raw_start:
                try:
                    # numeric epoch seconds
                    start_ts = int(raw_start)
                    start_dt = datetime.fromtimestamp(start_ts)
                except Exception:
                    # leave as None if parsing fails
                    start_dt = None

            raw_url = title_el["href"] if title_el and title_el.has_attr("href") else None
            if raw_url and raw_url.startswith("/"):
                abs_url = f"{URL}{raw_url}"
            else:
                abs_url = raw_url

            results.setdefault(category, []).append({
                "title": title_el.get_text(strip=True) if title_el else None,
                "url": abs_url,
                "course": course_el.get_text(strip=True) if course_el else None,
                "due_text": due_el.get_text(strip=True) if due_el else None,
                "start": start_dt,
                "locked": el.get("data-locked"),
                "exception": el.get("data-exception")
            })

            el = el.find_next_sibling()

    return results

def format_multi_child_summary(mode, child_summaries):
    """
    Render a summary that includes overdue_submissions, upcoming_submissions,
    and upcoming_events for each child.

    Returns a tuple: (plain_text_summary, html_summary)
    HTML shows clickable links with a short '🔗' shortcut.
    """
    text_lines = []
    html_lines = []

    text_lines.append(f"{mode.capitalize()} Schoology Summary\n")
    text_lines.append("Full details below.\n")

    html_lines.append(f"<h2>{mode.capitalize()} Schoology Summary</h2>")
    html_lines.append("<p>Full details below.</p>")

    for child_name, tasks in child_summaries.items():
        # Plain text header
        text_lines.append(f"\n👤 {child_name}\n")
        # HTML header
        html_lines.append(f"<h3>👤 {html.escape(child_name)}</h3>")

        # Overdue Submissions
        overdue = tasks.get("overdue_submissions", [])
        text_lines.append("\n🔴 Overdue Submissions:")
        html_lines.append("<h4>🔴 Overdue Submissions:</h4><ul>")
        if not overdue:
            text_lines.append("\n  • None")
            html_lines.append("<li>None</li>")
        else:
            for it in sorted(overdue, key=lambda x: (x['start'] or datetime.max)):
                date_str = it['start'].strftime('%a %b %d %I:%M %p') if it['start'] else "No date"
                title = it['title'] or ''
                course = it.get('course')
                url = it.get('url')

                t_line = f"\n  • {date_str} — {title}"
                if course:
                    t_line += f" ({course})"
                if url:
                    t_line += f" — {url}"
                text_lines.append(t_line)

                # HTML line with clickable short link (🔗)
                h_title = html.escape(title)
                h_course = f" ({html.escape(course)})" if course else ""
                h_date = html.escape(date_str)
                if url:
                    h_url = html.escape(url)
                    h_line = f"<li>{h_date} — {h_title}{h_course} — <a href=\"{h_url}\">🔗</a></li>"
                else:
                    h_line = f"<li>{h_date} — {h_title}{h_course}</li>"
                html_lines.append(h_line)
        html_lines.append("</ul>")

        # Upcoming Submissions
        upcoming_sub = tasks.get("upcoming_submissions", [])
        text_lines.append("\n\n🟡 Upcoming Submissions:")
        html_lines.append("<h4>🟡 Upcoming Submissions:</h4><ul>")
        if not upcoming_sub:
            text_lines.append("\n  • None")
            html_lines.append("<li>None</li>")
        else:
            for it in sorted(upcoming_sub, key=lambda x: (x['start'] or datetime.max)):
                date_str = it['start'].strftime('%a %b %d %I:%M %p') if it['start'] else "No date"
                title = it['title'] or ''
                course = it.get('course')
                url = it.get('url')
                due_text = it.get('due_text')

                t_line = f"\n  • {date_str} — {title}"
                if course:
                    t_line += f" ({course})"
                if url:
                    t_line += f" — {url}"
                if due_text:
                    t_line += f" [due: {due_text}]"
                text_lines.append(t_line)

                h_title = html.escape(title)
                h_course = f" ({html.escape(course)})" if course else ""
                h_date = html.escape(date_str)
                h_due = f" [due: {html.escape(due_text)}]" if due_text else ""
                if url:
                    h_url = html.escape(url)
                    h_line = f"<li>{h_date} — {h_title}{h_course}{h_due} — <a href=\"{h_url}\">🔗</a></li>"
                else:
                    h_line = f"<li>{h_date} — {h_title}{h_course}{h_due}</li>"
                html_lines.append(h_line)
        html_lines.append("</ul>")

        # Upcoming Events
        upcoming_ev = tasks.get("upcoming_events", [])
        text_lines.append("\n\n🔵 Upcoming Events:")
        html_lines.append("<h4>🔵 Upcoming Events:</h4><ul>")
        if not upcoming_ev:
            text_lines.append("\n  • None")
            html_lines.append("<li>None</li>")
        else:
            for it in sorted(upcoming_ev, key=lambda x: (x['start'] or datetime.max)):
                date_str = it['start'].strftime('%a %b %d %I:%M %p') if it['start'] else "No date"
                title = it['title'] or ''
                course = it.get('course')
                url = it.get('url')

                t_line = f"\n  • {date_str} — {title}"
                if course:
                    t_line += f" ({course})"
                if url:
                    t_line += f" — {url}"
                text_lines.append(t_line)

                h_title = html.escape(title)
                h_course = f" ({html.escape(course)})" if course else ""
                h_date = html.escape(date_str)
                if url:
                    h_url = html.escape(url)
                    h_line = f"<li>{h_date} — {h_title}{h_course} — <a href=\"{h_url}\">🔗</a></li>"
                else:
                    h_line = f"<li>{h_date} — {h_title}{h_course}</li>"
                html_lines.append(h_line)
        html_lines.append("</ul>")

        text_lines.append("\n" + ("-" * 40))
        html_lines.append("<hr>")

    text_summary = "\n".join(text_lines)
    html_summary = "<html><body>" + "\n".join(html_lines) + "</body></html>"

    return text_summary, html_summary

def send_email(text_body, html_body, email, mode):
    """
    Send a multipart/alternative email with both plain text and HTML.
    HTML uses short clickable '🔗' anchors for URLs.
    """
    msg = MIMEMultipart('alternative')
    mode_fmt = mode.capitalize()
    msg['Subject'] = f'{mode_fmt} Schoology Summary'
    msg['From'] = EMAIL_USER
    msg['To'] = email

    part1 = MIMEText(text_body, 'plain')
    part2 = MIMEText(html_body, 'html')

    msg.attach(part1)
    msg.attach(part2)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
            logger.info(f'Email sent successfully to {email}')
            return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f'Email authentication failed for {email}: {e}')
        return False
    except smtplib.SMTPException as e:
        logger.error(f'SMTP error sending to {email}: {e}')
        return False
    except Exception as e:
        logger.error(f'Unexpected error sending email to {email}: {e}')
        return False

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    logger.info('Starting scraper')

    args = parse_args()
    login()

    child_summaries = {}

    for child in CHILDREN:
        switch_child(child)
        child_name = child['name']

        # fetch Schoology tasks (overdue/upcoming submissions/events)
        tasks = fetch_schoology_tasks()
        child_summaries[child_name] = tasks

    text_summary, html_summary = format_multi_child_summary(args.mode, child_summaries)

    # Preview or send
    if os.getenv('PREVIEW_ONLY') == 'true':
        logger.info("Preview Only mode enabled - not sending any email")
        logger.info(text_summary)
    else:
        failed = []
        for email in EMAIL_TO:
            if not send_email(text_summary, html_summary, email, args.mode):
                failed.append(email)

        if failed:
            logger.error(f'Failed to send to: {", ".join(failed)}')
            sys.exit(1)


    logger.info('Finished')


if __name__ == '__main__':
    main()
