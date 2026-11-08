/* CampusDesk front-end behaviour. No dependencies. */
(function () {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ----- toasts (also survive a page reload via sessionStorage) ----- */
  function toast(message, kind) {
    let box = document.getElementById("toasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "toasts";
      box.className = "toasts";
      box.setAttribute("role", "status");
      document.body.appendChild(box);
    }
    const el = document.createElement("div");
    el.className = "toast" + (kind === "error" ? " error" : "");
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => {
      el.classList.add("out");
      setTimeout(() => el.remove(), 260);
    }, 3600);
  }
  window.cdToast = toast;

  function toastAfterReload(message) {
    try { sessionStorage.setItem("cd-toast", message); } catch (e) { /* storage may be blocked */ }
  }
  try {
    const pending = sessionStorage.getItem("cd-toast");
    if (pending) { sessionStorage.removeItem("cd-toast"); toast(pending); }
  } catch (e) { /* ignore */ }

  /* ----- API helper used by the ticket page ----- */
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  async function api(method, url, payload) {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfMeta ? csrfMeta.content : "" },
      body: payload ? JSON.stringify(payload) : undefined,
      credentials: "same-origin",
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* non-JSON error */ }
    if (!res.ok) throw new Error(data.error || "Something went wrong. Try again.");
    return data;
  }

  function busy(btn, on) {
    if (!btn) return;
    btn.classList.toggle("is-loading", on);
    btn.disabled = on;
  }

  /* ----- ticket page actions ----- */
  const ticketRoot = document.querySelector("[data-ticket-api]");
  if (ticketRoot) {
    const base = ticketRoot.dataset.ticketApi;
    const errorBox = document.getElementById("actionError");
    const fail = (e) => { if (errorBox) errorBox.textContent = e.message; toast(e.message, "error"); };

    ticketRoot.querySelectorAll("[data-status-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        busy(btn, true);
        api("PATCH", base + "/status", { status: btn.dataset.statusAction })
          .then(() => { toastAfterReload(btn.dataset.done || "Status updated"); location.reload(); })
          .catch((e) => { busy(btn, false); fail(e); });
      });
    });

    const assignBtn = document.getElementById("assignBtn");
    if (assignBtn) {
      assignBtn.addEventListener("click", () => {
        const id = parseInt(document.getElementById("staffSelect").value, 10);
        busy(assignBtn, true);
        api("PATCH", base + "/assign", { staff_id: id })
          .then(() => { toastAfterReload("Complaint assigned"); location.reload(); })
          .catch((e) => { busy(assignBtn, false); fail(e); });
      });
    }

    const form = document.getElementById("commentForm");
    if (form) {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const input = document.getElementById("commentBody");
        const btn = form.querySelector("button");
        if (!input.value.trim()) return;
        busy(btn, true);
        api("POST", base + "/comments", { body: input.value })
          .then(() => { toastAfterReload("Comment posted"); location.reload(); })
          .catch((e) => { busy(btn, false); fail(e); });
      });
    }
  }

  /* ----- generic form niceties ----- */
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector('button[type="submit"], button:not([type])');
      if (btn) setTimeout(() => busy(btn, true), 0);
    });
  });

  document.querySelectorAll("[data-autosubmit]").forEach((el) => {
    el.addEventListener("change", () => el.form.submit());
  });

  document.querySelectorAll("[data-pw-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.pwToggle);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
      btn.setAttribute("aria-pressed", String(show));
    });
  });

  document.querySelectorAll("[data-counter]").forEach((area) => {
    const out = document.getElementById(area.dataset.counter);
    const max = parseInt(area.getAttribute("maxlength") || "2000", 10);
    const update = () => { out.textContent = area.value.length + " / " + max; };
    area.addEventListener("input", update);
    update();
  });

  /* ----- landing page: a ticket travelling along the track ----- */
  const demo = document.getElementById("demoTrack");
  if (demo) {
    const items = Array.from(demo.querySelectorAll("li"));
    const caption = document.getElementById("demoCaption");
    const pill = document.getElementById("demoPill");
    const names = ["Open", "Assigned", "In Progress", "Resolved", "Closed"];
    const notes = [
      "You raise the complaint and get a ticket number straight away.",
      "An admin picks the right staff member and assigns it.",
      "The staff member starts work. Every change is written to the history.",
      "Staff mark it fixed. Nothing closes until you agree.",
      "You confirm the fix. If it is not fixed, reopen it with one click.",
    ];
    let step = 0;
    function show(i) {
      items.forEach((li, idx) => {
        li.classList.toggle("done", idx < i);
        li.classList.toggle("current", idx === i);
      });
      demo.style.setProperty("--pct", (i / (items.length - 1)) * 100 + "%");
      pill.textContent = names[i];
      pill.dataset.status = names[i];
      caption.textContent = notes[i];
    }
    show(0);
    if (!reduceMotion) {
      setInterval(() => { step = (step + 1) % items.length; show(step); }, 2600);
    } else {
      items.forEach((li, idx) => li.addEventListener("click", () => show(idx)));
    }
  }
})();
