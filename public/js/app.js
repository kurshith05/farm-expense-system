// Ask for confirmation before any form marked with data-confirm is submitted.
document.querySelectorAll("form[data-confirm]").forEach(function (form) {
  form.addEventListener("submit", function (event) {
    if (!confirm(form.dataset.confirm)) event.preventDefault();
  });
});

// Buttons marked data-print open the browser print dialog (choose "Save as PDF" there).
document.querySelectorAll("[data-print]").forEach(function (btn) {
  btn.addEventListener("click", function () { window.print(); });
});
