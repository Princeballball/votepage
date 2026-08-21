from django.conf import settings
from django.db import models
from django.utils import timezone


class Poll(models.Model):
    TYPE_CHOICES = [('text', '一般投票'), ('time', '時間投票')]
    RESULT_CHOICES = [('after_vote', '投票後即可看'), ('after_close', '截止後才可看')]
    title = models.CharField(max_length=200)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='polls',
    )
    poll_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    multiple = models.BooleanField(default=False)
    named_voting = models.BooleanField(default=False)
    allow_voter_options = models.BooleanField(default=False)
    deadline = models.DateTimeField(null=True, blank=True)
    result_visibility = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='after_vote',
    )
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def ended(self):
        return self.is_closed or bool(self.deadline and self.deadline <= timezone.now())

    def __str__(self):
        return self.title


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    display_text = models.CharField(max_length=200)
    date = models.DateField(null=True, blank=True)
    weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['poll', 'display_text'],
                name='unique_poll_option',
            ),
        ]


class Ballot(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='ballots')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ballots',
    )
    options = models.ManyToManyField(Option, related_name='ballots')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['poll', 'user'],
                name='one_ballot_per_user',
            ),
        ]

# Create your models here.
