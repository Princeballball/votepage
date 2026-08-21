(() => {
    const form = document.querySelector('#edit-poll-form');
    const list = document.querySelector('#edit-options');
    const output = document.querySelector('#edit-options-json');

    function bindRemove(button) {
        button.addEventListener('click', () => button.closest('.preview-item').remove());
    }

    document.querySelectorAll('.edit-option-remove').forEach(bindRemove);

    document.querySelector('#add-edit-option').addEventListener('click', () => {
        const row = document.createElement('div');
        row.className = 'preview-item';

        const input = document.createElement('input');
        input.className = 'edit-option-text';
        input.maxLength = 200;
        input.placeholder = '輸入新選項';

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'remove edit-option-remove';
        remove.textContent = '刪除';
        bindRemove(remove);

        row.append(input, remove);
        list.append(row);
        input.focus();
    });

    form.addEventListener('submit', event => {
        const options = [...document.querySelectorAll('.edit-option-text')]
            .map(input => ({
                id: input.dataset.optionId ? Number(input.dataset.optionId) : null,
                display_text: input.value.trim(),
            }))
            .filter(option => option.display_text);
        const uniqueTexts = new Set(options.map(option => option.display_text));

        if (options.length < 2 || uniqueTexts.size !== options.length) {
            event.preventDefault();
            window.alert('請保留至少兩個不重複的有效選項。');
            return;
        }

        output.value = JSON.stringify(options);
    });
})();
