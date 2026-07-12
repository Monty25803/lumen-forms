(function () {
  const typeSelect = document.getElementById('id_question_type');
  const optionsBuilder = document.getElementById('options-builder');
  const optionsList = document.getElementById('options-list');
  const addBtn = document.getElementById('add-option-btn');
  const template = document.getElementById('option-row-template');
  if (!typeSelect || !optionsBuilder || !optionsList || !addBtn || !template) return;

  const choiceTypes = new Set(['radio', 'checkbox', 'dropdown']);

  function refreshPlaceholders() {
    optionsList.querySelectorAll('.option-row input[name="options"]').forEach((input, index) => {
      input.placeholder = 'Option ' + (index + 1);
    });
  }

  function syncOptionsVisibility() {
    optionsBuilder.hidden = !choiceTypes.has(typeSelect.value);
  }

  addBtn.addEventListener('click', function () {
    optionsList.appendChild(template.content.cloneNode(true));
    refreshPlaceholders();
  });

  optionsList.addEventListener('click', function (event) {
    const btn = event.target.closest('.btn-remove-option');
    if (!btn) return;
    const rows = optionsList.querySelectorAll('.option-row');
    if (rows.length <= 2) return;
    btn.closest('.option-row').remove();
    refreshPlaceholders();
  });

  typeSelect.addEventListener('change', syncOptionsVisibility);
  syncOptionsVisibility();
  refreshPlaceholders();
})();
