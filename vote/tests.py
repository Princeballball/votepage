import json
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Ballot, Option, Poll


class VoteFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pass12345')
        self.voter = User.objects.create_user('voter', 'voter@example.com', 'pass12345')

    def create_poll(self, multiple=False):
        poll = Poll.objects.create(
            title='聚餐',
            creator=self.owner,
            poll_type='text',
            multiple=multiple,
        )
        a = Option.objects.create(poll=poll, display_text='火鍋', order=0)
        b = Option.objects.create(poll=poll, display_text='披薩', order=1)
        return poll, a, b

    def test_create_time_poll_keeps_structured_fields(self):
        self.client.force_login(self.owner)
        payload = [
            {
                'display_text': '禮拜一 10～12',
                'weekday': 1,
                'start_time': '10:00',
                'end_time': '12:00',
            },
            {
                'display_text': '禮拜二 10～12',
                'weekday': 2,
                'start_time': '10:00',
                'end_time': '12:00',
            },
        ]
        response = self.client.post(reverse('poll_create'), {
            'title': '下週時間',
            'poll_type': 'time',
            'multiple': 'on',
            'result_visibility': 'after_vote',
            'options_json': json.dumps(payload),
        })
        self.assertEqual(response.status_code, 302)
        poll = Poll.objects.get(title='下週時間')
        self.assertTrue(poll.multiple)
        self.assertEqual(poll.options.get(weekday=1).start_time.hour, 10)

    def test_second_vote_updates_instead_of_adding_ballot(self):
        poll, a, b = self.create_poll()
        self.client.force_login(self.voter)
        self.client.post(reverse('poll_detail', args=[poll.pk]), {'options': [a.pk]})
        self.client.post(reverse('poll_detail', args=[poll.pk]), {'options': [b.pk]})
        self.assertEqual(Ballot.objects.filter(poll=poll, user=self.voter).count(), 1)
        self.assertEqual(list(Ballot.objects.get(poll=poll, user=self.voter).options.all()), [b])

    def test_single_choice_rejects_multiple_options(self):
        poll, a, b = self.create_poll()
        self.client.force_login(self.voter)
        self.client.post(reverse('poll_detail', args=[poll.pk]), {'options': [a.pk, b.pk]})
        self.assertFalse(Ballot.objects.exists())

    def test_closed_and_expired_polls_reject_votes(self):
        poll, a, _ = self.create_poll()
        poll.deadline = timezone.now() - timedelta(minutes=1); poll.save()
        self.client.force_login(self.voter)
        self.client.post(reverse('poll_detail', args=[poll.pk]), {'options': [a.pk]})
        self.assertFalse(Ballot.objects.exists())

    def test_only_owner_can_close(self):
        poll, _, _ = self.create_poll()
        self.client.force_login(self.voter)
        self.assertEqual(self.client.post(reverse('poll_close', args=[poll.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse('poll_close', args=[poll.pk]))
        poll.refresh_from_db(); self.assertTrue(poll.is_closed)

    def test_owner_can_edit_poll_and_options(self):
        poll, first, second = self.create_poll(multiple=True)
        Ballot.objects.create(poll=poll, user=self.voter).options.add(first, second)
        self.client.force_login(self.owner)
        options = [
            {'id': first.pk, 'display_text': '壽喜燒'},
            {'id': second.pk, 'display_text': '披薩'},
            {'id': None, 'display_text': '義大利麵'},
        ]
        response = self.client.post(reverse('poll_edit', args=[poll.pk]), {
            'title': '晚餐吃什麼',
            'named_voting': 'on',
            'result_visibility': 'after_vote',
            'options_json': json.dumps(options),
        })
        self.assertEqual(response.status_code, 302)
        poll.refresh_from_db()
        self.assertEqual(poll.title, '晚餐吃什麼')
        self.assertTrue(poll.named_voting)
        self.assertFalse(poll.multiple)
        self.assertEqual(poll.options.count(), 3)
        self.assertEqual(Ballot.objects.get(poll=poll).options.count(), 1)

    def test_non_owner_cannot_edit_poll(self):
        poll, _, _ = self.create_poll()
        self.client.force_login(self.voter)
        self.assertEqual(self.client.get(reverse('poll_edit', args=[poll.pk])).status_code, 404)

    def test_named_results_show_voter_name(self):
        poll, first, _ = self.create_poll()
        poll.named_voting = True
        poll.save(update_fields=['named_voting'])
        ballot = Ballot.objects.create(poll=poll, user=self.voter)
        ballot.options.add(first)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('poll_detail', args=[poll.pk]))
        self.assertContains(response, 'voter')

    def test_voter_can_add_option_when_owner_allows_it(self):
        poll, _, _ = self.create_poll()
        poll.allow_voter_options = True
        poll.save(update_fields=['allow_voter_options'])
        self.client.force_login(self.voter)

        response = self.client.post(
            reverse('poll_option_add', args=[poll.pk]),
            {'display_text': '燒肉'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(poll.options.filter(display_text='燒肉').exists())

    def test_voter_cannot_add_option_without_permission(self):
        poll, _, _ = self.create_poll()
        self.client.force_login(self.voter)
        self.client.post(
            reverse('poll_option_add', args=[poll.pk]),
            {'display_text': '燒肉'},
        )
        self.assertFalse(poll.options.filter(display_text='燒肉').exists())

    def test_voter_cannot_add_duplicate_option(self):
        poll, _, _ = self.create_poll()
        poll.allow_voter_options = True
        poll.save(update_fields=['allow_voter_options'])
        self.client.force_login(self.voter)
        self.client.post(
            reverse('poll_option_add', args=[poll.pk]),
            {'display_text': '火鍋'},
        )
        self.assertEqual(poll.options.filter(display_text='火鍋').count(), 1)

    def test_create_poll_accepts_separate_deadline_date_and_time(self):
        self.client.force_login(self.owner)
        tomorrow = timezone.localtime() + timedelta(days=1)
        response = self.client.post(reverse('poll_create'), {
            'title': '有截止時間的投票',
            'poll_type': 'text',
            'result_visibility': 'after_vote',
            'deadline_date': tomorrow.strftime('%Y-%m-%d'),
            'deadline_time': '18:30',
            'options_json': json.dumps([
                {'display_text': '選項一'},
                {'display_text': '選項二'},
            ]),
        })
        self.assertEqual(response.status_code, 302)
        poll = Poll.objects.get(title='有截止時間的投票')
        self.assertEqual(timezone.localtime(poll.deadline).strftime('%H:%M'), '18:30')

    def test_deadline_requires_both_date_and_time(self):
        self.client.force_login(self.owner)
        tomorrow = timezone.localtime() + timedelta(days=1)
        response = self.client.post(reverse('poll_create'), {
            'title': '錯誤截止時間',
            'poll_type': 'text',
            'result_visibility': 'after_vote',
            'deadline_date': tomorrow.strftime('%Y-%m-%d'),
            'options_json': json.dumps([
                {'display_text': '選項一'},
                {'display_text': '選項二'},
            ]),
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            '請同時選擇截止日期和截止時間',
            status_code=400,
        )

    def test_poll_with_deadline_displays_countdown(self):
        poll, _, _ = self.create_poll()
        poll.deadline = timezone.now() + timedelta(hours=2)
        poll.save(update_fields=['deadline'])

        response = self.client.get(reverse('poll_detail', args=[poll.pk]))

        self.assertContains(response, 'id="deadline-countdown"')
        self.assertContains(response, '距離投票截止')

    def test_poll_list_displays_deadline_date_and_time(self):
        poll, _, _ = self.create_poll()
        poll.deadline = timezone.make_aware(datetime(2026, 8, 25, 18, 30))
        poll.save(update_fields=['deadline'])
        self.client.force_login(self.owner)

        response = self.client.get(reverse('poll_list'))

        self.assertContains(response, '截止：2026/08/25 18:30')
