import json
from datetime import datetime
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import RegisterForm
from .models import Ballot, Option, Poll


def parse_deadline(request, errors):
    deadline_date = request.POST.get('deadline_date', '').strip()
    deadline_time = request.POST.get('deadline_time', '').strip()

    if not deadline_date and not deadline_time:
        return None
    if not deadline_date or not deadline_time:
        errors.append('請同時選擇截止日期和截止時間。')
        return None

    try:
        deadline = timezone.make_aware(
            datetime.fromisoformat(f'{deadline_date}T{deadline_time}')
        )
    except ValueError:
        errors.append('截止日期或時間格式無效。')
        return None

    if deadline <= timezone.now():
        errors.append('截止時間必須晚於現在。')
    return deadline


def home(request):
    return redirect('poll_list' if request.user.is_authenticated else 'login')


def register(request):
    if request.user.is_authenticated:
        return redirect('poll_list')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('poll_list')
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('poll_list')
    error = None
    if request.method == 'POST':
        identity = request.POST.get('identity', '').strip()
        username = (
            User.objects.filter(email__iexact=identity)
            .values_list('username', flat=True)
            .first()
            or identity
        )
        user = authenticate(request, username=username, password=request.POST.get('password'))
        if user:
            login(request, user)
            return redirect(request.GET.get('next') or 'poll_list')
        error = '帳號或密碼錯誤'
    return render(request, 'registration/login.html', {'error': error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def poll_list(request):
    polls = request.user.polls.annotate(voter_count=Count('ballots')).order_by('-created_at')
    return render(request, 'polls/list.html', {'polls': polls})


@login_required
def poll_create(request):
    if request.method == 'GET':
        return render(request, 'polls/create.html')
    title = request.POST.get('title', '').strip()
    poll_type = request.POST.get('poll_type')
    multiple = request.POST.get('multiple') == 'on'
    named_voting = request.POST.get('named_voting') == 'on'
    allow_voter_options = request.POST.get('allow_voter_options') == 'on'
    visibility = request.POST.get('result_visibility')
    try:
        raw_options = json.loads(request.POST.get('options_json', '[]'))
    except json.JSONDecodeError:
        raw_options = []
    cleaned, seen = [], set()
    for item in raw_options:
        text = str(item.get('display_text', '')).strip()
        if text and text not in seen:
            item['display_text'] = text
            cleaned.append(item)
            seen.add(text)
    errors = []
    if not title:
        errors.append('請輸入投票標題。')
    if poll_type not in dict(Poll.TYPE_CHOICES):
        errors.append('投票類型無效。')
    if visibility not in dict(Poll.RESULT_CHOICES):
        errors.append('結果顯示設定無效。')
    if len(cleaned) < 2:
        errors.append('請建立至少兩個不重複的有效選項。')
    deadline = parse_deadline(request, errors)
    if errors:
        return render(
            request,
            'polls/create.html',
            {'errors': errors, 'posted': request.POST},
            status=400,
        )
    with transaction.atomic():
        poll = Poll.objects.create(
            title=title,
            creator=request.user,
            poll_type=poll_type,
            multiple=multiple, named_voting=named_voting, deadline=deadline,
            result_visibility=visibility,
            allow_voter_options=allow_voter_options,
        )
        for index, item in enumerate(cleaned):
            Option.objects.create(
                poll=poll,
                display_text=item['display_text'],
                date=item.get('date') or None,
                weekday=item.get('weekday'),
                start_time=item.get('start_time') or None,
                end_time=item.get('end_time') or None,
                order=index,
            )
    messages.success(request, '投票已建立，現在可以分享連結。')
    return redirect('poll_detail', pk=poll.pk)


def poll_detail(request, pk):
    poll = get_object_or_404(Poll.objects.select_related('creator'), pk=pk)
    ballot = None
    if request.user.is_authenticated:
        ballot = (
            Ballot.objects.filter(poll=poll, user=request.user)
            .prefetch_related('options')
            .first()
        )
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        if poll.ended:
            messages.error(request, '這份投票已經結束。')
            return redirect('poll_detail', pk=pk)
        option_ids = request.POST.getlist('options')
        options = list(poll.options.filter(pk__in=option_ids))
        invalid_selection = (
            not options
            or len(options) != len(set(option_ids))
            or (not poll.multiple and len(options) != 1)
        )
        if invalid_selection:
            messages.error(request, '請選擇有效的投票選項。')
            return redirect('poll_detail', pk=pk)
        with transaction.atomic():
            locked = Poll.objects.select_for_update().get(pk=poll.pk)
            if locked.ended:
                return HttpResponseBadRequest('投票已結束')
            ballot, _ = Ballot.objects.get_or_create(poll=locked, user=request.user)
            ballot.options.set(options)
        messages.success(request, '你的投票已更新。')
        return redirect('poll_detail', pk=pk)
    options = poll.options.annotate(
        vote_count=Count('ballots')
    ).prefetch_related('ballots__user')
    selected = set(ballot.options.values_list('id', flat=True)) if ballot else set()
    can_results = (
        request.user == poll.creator
        or poll.ended
        or (poll.result_visibility == 'after_vote' and ballot)
    )
    max_votes = max((o.vote_count for o in options), default=0)
    for option in options:
        option.percent = round(option.vote_count / max_votes * 100) if max_votes else 0
        option.voter_names = (
            [vote.user.username for vote in option.ballots.all()]
            if poll.named_voting
            else []
        )
    return render(request, 'polls/detail.html', {
        'poll': poll,
        'options': options,
        'selected': selected,
        'can_results': can_results,
        'voter_count': poll.ballots.count(),
    })


@login_required
def poll_edit(request, pk):
    poll = get_object_or_404(
        Poll.objects.prefetch_related('options'),
        pk=pk,
        creator=request.user,
    )
    if poll.ended:
        messages.error(request, '已結束的投票不能修改。')
        return redirect('poll_detail', pk=pk)

    if request.method == 'GET':
        return render(request, 'polls/edit.html', {'poll': poll})

    title = request.POST.get('title', '').strip()
    multiple = request.POST.get('multiple') == 'on'
    named_voting = request.POST.get('named_voting') == 'on'
    allow_voter_options = request.POST.get('allow_voter_options') == 'on'
    visibility = request.POST.get('result_visibility')
    try:
        raw_options = json.loads(request.POST.get('options_json', '[]'))
    except json.JSONDecodeError:
        raw_options = []

    cleaned, seen, errors = [], set(), []
    existing_ids = set(poll.options.values_list('id', flat=True))
    for item in raw_options:
        text = str(item.get('display_text', '')).strip()
        option_id = item.get('id')
        if option_id is not None and option_id not in existing_ids:
            errors.append('選項資料無效。')
            continue
        if text and text not in seen:
            cleaned.append({'id': option_id, 'display_text': text})
            seen.add(text)

    if not title:
        errors.append('請輸入投票標題。')
    if visibility not in dict(Poll.RESULT_CHOICES):
        errors.append('結果顯示設定無效。')
    if len(cleaned) < 2:
        errors.append('請保留至少兩個不重複的有效選項。')

    deadline = parse_deadline(request, errors)

    if errors:
        return render(request, 'polls/edit.html', {
            'poll': poll,
            'errors': errors,
            'posted': request.POST,
        }, status=400)

    with transaction.atomic():
        locked = Poll.objects.select_for_update().get(pk=poll.pk, creator=request.user)
        if locked.ended:
            return HttpResponseBadRequest('投票已結束')

        locked.title = title
        locked.multiple = multiple
        locked.named_voting = named_voting
        locked.allow_voter_options = allow_voter_options
        locked.deadline = deadline
        locked.result_visibility = visibility
        locked.save(update_fields=[
            'title', 'multiple', 'named_voting', 'allow_voter_options', 'deadline',
            'result_visibility',
        ])

        retained_existing_ids = [
            item['id'] for item in cleaned if item['id'] is not None
        ]
        for option in locked.options.filter(pk__in=retained_existing_ids):
            option.display_text = f'__editing_option_{option.pk}__'
            option.save(update_fields=['display_text'])

        kept_ids = []
        for index, item in enumerate(cleaned):
            if item['id'] is None:
                option = Option.objects.create(
                    poll=locked,
                    display_text=item['display_text'],
                    order=index,
                )
            else:
                option = Option.objects.get(pk=item['id'], poll=locked)
                option.display_text = item['display_text']
                option.order = index
                option.save(update_fields=['display_text', 'order'])
            kept_ids.append(option.pk)

        locked.options.exclude(pk__in=kept_ids).delete()
        locked.ballots.annotate(
            option_count=Count('options')
        ).filter(option_count=0).delete()

        if not multiple:
            for existing_ballot in locked.ballots.prefetch_related('options'):
                chosen = existing_ballot.options.order_by('order', 'id').first()
                if chosen:
                    existing_ballot.options.set([chosen])

    messages.success(request, '投票內容已更新。')
    return redirect('poll_detail', pk=pk)


@login_required
@require_POST
def poll_option_add(request, pk):
    display_text = request.POST.get('display_text', '').strip()
    if not display_text:
        messages.error(request, '請輸入選項內容。')
        return redirect('poll_detail', pk=pk)
    if len(display_text) > 200:
        messages.error(request, '選項內容不可超過 200 個字。')
        return redirect('poll_detail', pk=pk)

    try:
        with transaction.atomic():
            poll = get_object_or_404(Poll.objects.select_for_update(), pk=pk)
            if poll.ended:
                messages.error(request, '這份投票已經結束。')
            elif not poll.allow_voter_options:
                messages.error(request, '建立者沒有開放新增選項。')
            elif poll.options.filter(display_text=display_text).exists():
                messages.error(request, '這個選項已經存在。')
            else:
                next_order = poll.options.aggregate(highest=Max('order'))['highest']
                Option.objects.create(
                    poll=poll,
                    display_text=display_text,
                    order=(next_order + 1) if next_order is not None else 0,
                )
                messages.success(request, '選項已新增。')
    except IntegrityError:
        messages.error(request, '這個選項已經存在。')

    return redirect('poll_detail', pk=pk)


@login_required
@require_POST
def poll_close(request, pk):
    poll = get_object_or_404(Poll, pk=pk, creator=request.user)
    poll.is_closed = True
    poll.save(update_fields=['is_closed'])
    messages.success(request, '投票已關閉。')
    return redirect('poll_detail', pk=pk)
