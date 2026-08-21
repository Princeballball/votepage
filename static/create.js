(() => {
    let options = [];
    let dates = [];
    const $ = selector => document.querySelector(selector);
    const $$ = selector => [...document.querySelectorAll(selector)];
    const names = [
        '',
        '禮拜一',
        '禮拜二',
        '禮拜三',
        '禮拜四',
        '禮拜五',
        '禮拜六',
        '禮拜日',
    ];
    const short = ['日', '一', '二', '三', '四', '五', '六'];

    function timeText(time) {
        return time.endsWith(':00')
            ? String(Number(time.slice(0, 2)))
            : time;
    }

    function render() {
        const box = $('#preview');
        box.innerHTML = '';
        options.forEach((option, index) => {
            const row = document.createElement('div');
            row.className = 'preview-item';
            const input = document.createElement('input');
            input.value = option.display_text;
            input.maxLength=200;
            input.oninput = () => {
                option.display_text = input.value;
                sync();
            };
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'remove';
            remove.textContent = '刪除';
            remove.onclick = () => {
                options.splice(index, 1);
                render();
            };
            row.append(input, remove);
            box.append(row);
        });
        $('#option-count').textContent = options.length;
        sync();
    }

    function sync() {
        $('#options-json').value = JSON.stringify(options);
    }

    function addText(value = '') {
        options.push({
            display_text: value,
        });
        render();
    }

    function addSlot(start = '10:00', end = '12:00') {
        const row = document.createElement('div');
        row.className = 'slot';
        row.innerHTML = `
            <label>
                開始時間
                <input type="time" class="slot-start" value="${start}" required>
            </label>
            <label>
                結束時間
                <input type="time" class="slot-end" value="${end}" required>
            </label>
            <button type="button" class="remove">刪除</button>
        `;
        row.querySelector('button').onclick = () => {
            row.remove();
            updateCount();
        };
        row.querySelectorAll('input').forEach(input => {
            input.oninput = updateCount;
        });
        $('#slots').append(row);
        updateCount();
    }

    function targets() {
        if ($('[name=date_mode]:checked').value === 'weekday') {
            return $$('#weekday-mode input:checked').map(input => ({
                weekday: Number(input.value),
                label: names[Number(input.value)],
            }));
        }
        return dates.map(value => {
            const date = new Date(`${value}T12:00:00`);
            return {
                date: value,
                label: `${date.getMonth() + 1}/${date.getDate()}（${short[date.getDay()]}）`,
            };
        });
    }

    function slots() {
        return $$('.slot').map(row=>({
            start_time: row.querySelector('.slot-start').value,
            end_time: row.querySelector('.slot-end').value,
        })).filter(slot => (
            slot.start_time
            && slot.end_time
            && slot.start_time < slot.end_time
        ));
    }

    function updateCount() {
        const count = targets().length * slots().length;
        $('#generate').textContent = `產生 ${count} 個時間選項`;
        $('#generate-note').textContent = count ? '將加入現有選項，不會覆蓋' : '';
    }

    $$('[name=poll_type]').forEach(r => r.onchange = () => {
        const time = r.value === 'time' && r.checked;
        $('#text-builder').classList.toggle('hidden', time);
        $('#time-builder').classList.toggle('hidden', !time);
        $('#multiple').checked = time;
        updateCount();
    });
    $$('[name=date_mode]').forEach(r=>r.onchange=()=>{
        $('#weekday-mode').classList.toggle('hidden',r.value==='date'&&r.checked);
        $('#date-mode').classList.toggle('hidden',r.value==='weekday'&&r.checked);
        updateCount()
    });
    $('#add-text').onclick=()=>addText();
    $('#add-slot').onclick=()=>addSlot('13:00','15:00');
    $('#clear-options').onclick=()=>{
        options=[];
        render()
    };
    $$('.weekdays input').forEach(x=>x.onchange=updateCount);
    $$('.quick button').forEach(b=>b.onclick=()=>{
        const selected=b.dataset.days.split(',');
        $$('.weekdays input').forEach(x=>x.checked=selected.includes(x.value));
        updateCount()
    });
    function renderDates() {
        $('#dates').innerHTML='';
        dates.forEach((d,i)=>{
            const date=new Date(d+'T12:00:00'),b=document.createElement('button');
            b.type='button';
            b.className='chip';
            b.textContent=`${date.getMonth()+1}/${date.getDate()}（${short[date.getDay()]}） ×`;
            b.onclick=()=>{
                dates.splice(i,1);
                renderDates()
            };
            $('#dates').append(b)
        });
        updateCount()
    }

    $('#add-date').onclick = () => {
        const d=$('#date-input').value;
        if(d&&!dates.includes(d)){
            dates.push(d);
            dates.sort();
            renderDates()
        }
    };
    $('#split').onclick=()=>{
        const start = $('#split-start').value;
        const end = $('#split-end').value;
        const hours = Number($('#split-hours').value);
        let current = start.split(':').reduce((total, part) => total * 60 + Number(part));
        const final = end.split(':').reduce((total, part) => total * 60 + Number(part));
        const step = hours * 60;
        if (!step || current >= final) return;

        while (current + step <= final) {
            const formatTime = minutes => {
                const hour = String(Math.floor(minutes / 60)).padStart(2, '0');
                const minute = String(minutes % 60).padStart(2, '0');
                return `${hour}:${minute}`;
            };
            addSlot(formatTime(current), formatTime(current + step));
            current += step;
        }
    };
    $('#generate').onclick=()=>{
        const existing=new Set(options.map(o=>o.display_text.trim())),made=[];
        let skipped=0;
        for(const t of targets())for(const s of slots()){
            const text=`${t.label} ${timeText(s.start_time)}～${timeText(s.end_time)}`;
            if(existing.has(text)){
                skipped++;
                continue
            }existing.add(text);
            made.push({
                ...t,...s,display_text:text
            })
        }options.push(...made);
        $('#duplicate-note').textContent=skipped?`已略過 ${skipped} 個重複選項`:'';
        render()
    };
    $('#poll-form').onsubmit=e=>{
        sync();
        const texts=options.map(o=>o.display_text.trim()).filter(Boolean);
        if(texts.length<2||new Set(texts).size!==texts.length){
            e.preventDefault();
            alert('請建立至少兩個不重複的有效選項。')
        }
    };
    addText();
    addText();
    addSlot();
    render();
})();
