// Lightweight client-side validation for the prediction form.
(function () {
  const form = document.getElementById("predict-form");
  if (!form) return;
  form.addEventListener("submit", function (event) {
    const required = ["age", "restingbp", "cholesterol", "fastingbs", "maxhr", "oldpeak"];
    for (const name of required) {
      const el = form.elements[name];
      if (!el || !el.value) {
        event.preventDefault();
        el && el.focus();
        alert(`Field "${name}" is required.`);
        return false;
      }
    }
    return true;
  });
})();