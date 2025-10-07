import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import scrape as se

class TestSchoologyEmailer(unittest.TestCase):

    def test_get_tomorrow_range(self):
        start, end = se.get_tomorrow_range()
        expected_start = datetime.now() + timedelta(days=1)
        self.assertEqual(datetime.fromtimestamp(start).date(), expected_start.date())
        self.assertEqual(end - start, 86400)

    def test_get_next_week_range(self):
        start, end = se.get_next_week_range()
        start_dt = datetime.fromtimestamp(start)
        self.assertEqual(start_dt.weekday(), 0)  # Monday
        self.assertEqual(end - start, 86400 * 6)

    def test_get_this_week_range(self):
        start, end = se.get_this_week_range()
        start_dt = datetime.fromtimestamp(start)
        self.assertEqual(start_dt.weekday(), 0)
        self.assertEqual(end - start, 86400 * 6)

    @patch('scrape.SESSION.get')
    def test_get_calendar_parsing(self, mock_get):
        mock_get.return_value.json.return_value = [{
            'titleText': 'Test Assignment',
            'start': '2025-10-08 09:00:00',
            'content_title': 'Math',
            'body': '<p>Complete the worksheet</p>',
            'e_type': 'assignment'
        }]
        events = se.get_calendar(0, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Test Assignment')
        self.assertEqual(events[0]['course'], 'Math')
        self.assertEqual(events[0]['description'], 'Complete the worksheet')

    def test_format_multi_child_summary(self):
        events = [{
            'title': 'Test',
            'start': datetime(2025, 10, 8, 9, 0),
            'course': 'Math',
            'type': 'assignment',
            'description': 'Do it'
        }]
        summary = se.format_multi_child_summary('weekly', {'Alice': events})
        self.assertIn('📅 **Weekly Schoology Summary**', summary)
        self.assertIn('👤 **Alice**', summary)
        self.assertIn('**Test**', summary)
        self.assertIn('↪ Do it', summary)

    @patch('smtplib.SMTP_SSL')
    def test_send_email(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        se.send_email("Body text", "test@example.com", "weekly")
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @patch('scrape.login')
    @patch('scrape.switch_child')
    @patch('scrape.get_calendar')
    @patch('scrape.send_email')
    @patch('scrape.parse_args')
    @patch('scrape.EMAIL_TO', ['test@example.com'])
    @patch('scrape.CHILDREN', [{'name': 'Alice', 'id': '123'}])
    def test_main_preview_mode(self, mock_args, mock_send, mock_calendar, mock_switch, mock_login):
        mock_args.return_value.mode = 'tomorrow'
        mock_calendar.return_value = [{
            'title': 'Test',
            'start': datetime(2025, 10, 8, 9, 0),
            'course': 'Math',
            'type': 'assignment',
            'description': 'Do it'
        }]
        with patch.dict('os.environ', {'PREVIEW_ONLY': 'true'}):
            with patch('builtins.print') as mock_print:
                se.main()
                mock_send.assert_not_called()
                mock_print.assert_any_call("Preview Only mode enabled - not sending any email")

if __name__ == '__main__':
    unittest.main()