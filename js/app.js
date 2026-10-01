(function () {
  "use strict";

  // Mobile menu toggle
  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Confirm destructive actions and show a loading label on submit buttons
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    var button = form.querySelector("[data-loading]");
    if (button && form.checkValidity()) {
      setTimeout(function () {
        button.disabled = true;
        button.textContent = button.getAttribute("data-loading");
      }, 0);
    }
  });

  // Re-enable buttons if the page is restored from the back/forward cache
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      document.querySelectorAll("[data-loading]").forEach(function (b) { b.disabled = false; });
    }
  });

  // Month pickers and filters submit when changed
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () {
      if (el.form && el.value !== "" || el.tagName === "SELECT") { el.form.submit(); }
    });
  });

  // Print button on the report page
  document.querySelectorAll("[data-print]").forEach(function (el) {
    el.addEventListener("click", function () { window.print(); });
  });

  // Passwords must match on the registration form (the server checks too)
  var confirmField = document.getElementById("confirm_password");
  var passwordField = document.getElementById("password");
  if (confirmField && passwordField) {
    var check = function () {
      confirmField.setCustomValidity(
        confirmField.value && confirmField.value !== passwordField.value ? "Passwords do not match." : ""
      );
    };
    passwordField.addEventListener("input", check);
    confirmField.addEventListener("input", check);
  }

  // Success and info messages fade away; errors and warnings stay
  document.querySelectorAll(".flash-success, .flash-info").forEach(function (el) {
    setTimeout(function () { el.style.display = "none"; }, 7000);
  });
})();
