# 📚 Schoology Calendar Summary Emailer

**Author**: Matt Moss  
**License**: MIT  
**Version**: 1.0.0  
**Created**: October 2025

## 🧠 Overview

This script logs into Schoology as a parent, switches between multiple children, and sends a structured email summary of upcoming assignments. It supports two modes:

- `weekly`: Summarizes the upcoming week (ideal for Sunday mornings)
- `tomorrow`: Sends a daily reminder of tomorrow’s events

Email content is grouped by child, with short titles at the top and full details below.

---

## 🚀 Features

- 🔐 Secure credential loading via `.env`
- 👨‍👩‍👧‍👧 Multi-child support with per-child summaries
- 📅 Weekly and daily modes via CLI
- 📬 Email delivery via Gmail SMTP
- 🧪 Preview mode for testing without sending
- 🧵 Clean formatting for email clients

---

## 🛠️ Setup

### 1. Clone the repo

```bash
git clone https://github.com/mmoss82/schoology-summary-emailer.git
cd schoology-summary-emailer
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create .env file

```Env
SCHOOLOGY_USER=your_schoology_email
SCHOOLOGY_PASS=your_schoology_password
EMAIL_USER=your_gmail_address
EMAIL_PASS=your_gmail_app_password
EMAIL_TO=["parent1@example.com","parent2@example.com"]
CHILDREN=[{"name":"Jackson","id":"7654321"},{"name":"Brevin","id":"1234567"}}]
```

### 🔐 Use a Gmail App Password if 2FA is enabled.

## Usage

### Weekly Summary (Sunday morning)
```bash
python schoology.py --mode weekly
```

### Daily Reminder (every morning)
```bash
python schoology.py --mode tomorrow
```

### Preview without sending
```bash
PREVIEW_ONLY=true python schoology.py --mode tomorrow
```

### 🕒 Cron Jobs

## Weekly (Sunday 7:00 AM)
```bash
0 7 * * SUN /usr/bin/python3 /path/to/schoology.py --mode weekly
```

## Daily (6:30 AM)
```bash
30 6 * * * /usr/bin/python3 /path/to/schoology.py --mode tomorrow
```


## ✅ Redirect output to a log file for debugging:
```bash
0 7 * * SUN /usr/bin/python3 /path/to/schoology.py --mode weekly >> /path/to/log.txt 2>&1
```

## 📄 License

MIT License. See LICENSE file for details.

## 🤝 Contributing
Pull requests are welcome! If you’d like to add features like PDF attachments, HTML email formatting, or Schoology API integration, feel free to fork and submit a PR.


## 🙌 Acknowledgments
Built for busy parents who want clarity without clutter. Inspired by real-world school chaos and the need for better automation.


