(() => {
  const body = document.body;
  const sidebar = document.querySelector("#sidebar");
  const overlay = document.querySelector("#mobileOverlay");
  const collapseButton = document.querySelector("#sidebarCollapse");
  const mobileMenuButton = document.querySelector("#mobileMenuButton");
  const globalSearch = document.querySelector("#globalSearch");
  const helpButton = document.querySelector("#helpButton");
  const helpPopover = document.querySelector("#helpPopover");
  const notificationButton = document.querySelector("#notificationButton");
  const notificationPopover = document.querySelector("#notificationPopover");
  const notificationPreview = document.querySelector("#notificationPreview");
  const notificationBadge = document.querySelector("#notificationBadge");

  const readCookie = name => document.cookie
    .split(";")
    .map(item => item.trim())
    .find(item => item.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";
  const csrfToken = () => decodeURIComponent(
    readCookie("caed_pp_csrf") || document.querySelector('meta[name="csrf-token"]')?.content || ""
  );
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const method = String(init.method || "GET").toUpperCase();
    const target = typeof input === "string" ? new URL(input, window.location.href) : new URL(input.url, window.location.href);
    if (target.origin === window.location.origin && !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
      const headers = new Headers(init.headers || (typeof input !== "string" ? input.headers : undefined));
      if (!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", csrfToken());
      init = {...init, headers};
    }
    return originalFetch(input, init);
  };

  document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(form => {
    if (form.querySelector('input[name="_csrf"]')) return;
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "_csrf";
    hidden.value = csrfToken();
    form.prepend(hidden);
    form.addEventListener("submit", () => { hidden.value = csrfToken(); });
  });

  const closeMobileMenu = () => {
    sidebar?.classList.remove("is-open");
    overlay?.classList.remove("is-visible");
  };

  const closePopovers = except => {
    [[helpButton, helpPopover], [notificationButton, notificationPopover]].forEach(([button, panel]) => {
      if (!panel || panel === except) return;
      panel.hidden = true;
      button?.setAttribute("aria-expanded", "false");
    });
  };

  collapseButton?.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 850px)").matches) {
      closeMobileMenu();
      return;
    }
    body.classList.toggle("sidebar-collapsed");
    try {
      localStorage.setItem("caed-sidebar-collapsed", body.classList.contains("sidebar-collapsed") ? "1" : "0");
    } catch (_) {}
  });

  mobileMenuButton?.addEventListener("click", () => {
    sidebar?.classList.add("is-open");
    overlay?.classList.add("is-visible");
  });
  overlay?.addEventListener("click", closeMobileMenu);

  try {
    if (localStorage.getItem("caed-sidebar-collapsed") === "1" && !window.matchMedia("(max-width: 850px)").matches) {
      body.classList.add("sidebar-collapsed");
    }
  } catch (_) {}

  const routeSearch = value => {
    const localProcessSearch = document.querySelector("#processSearch");
    if (localProcessSearch) {
      localProcessSearch.value = value;
      localProcessSearch.dispatchEvent(new Event("input", {bubbles: true}));
      return true;
    }
    const catalogSearch = document.querySelector("#catalogSearch");
    if (catalogSearch) {
      catalogSearch.value = value;
      catalogSearch.dispatchEvent(new Event("input", {bubbles: true}));
      return true;
    }
    const profileFilter = document.querySelector("#profileFilter");
    if (profileFilter) {
      const normalized = value.trim().toLocaleLowerCase("pt-BR");
      const option = [...profileFilter.options].find(item => item.textContent.toLocaleLowerCase("pt-BR").includes(normalized));
      if (option && normalized) {
        profileFilter.value = option.value;
        profileFilter.dispatchEvent(new Event("change", {bubbles: true}));
        return true;
      }
    }
    return false;
  };

  globalSearch?.addEventListener("input", event => routeSearch(event.target.value));
  globalSearch?.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (!routeSearch(event.currentTarget.value) && event.currentTarget.value.trim()) {
      window.location.href = `/processes?query=${encodeURIComponent(event.currentTarget.value.trim())}`;
    }
  });

  const togglePopover = (button, panel) => {
    if (!button || !panel) return;
    const willOpen = panel.hidden;
    closePopovers(willOpen ? panel : null);
    panel.hidden = !willOpen;
    button.setAttribute("aria-expanded", String(willOpen));
  };

  helpButton?.addEventListener("click", event => {
    event.stopPropagation();
    togglePopover(helpButton, helpPopover);
  });

  const formatDate = value => {
    try {
      return new Intl.DateTimeFormat("pt-BR", {dateStyle: "short", timeStyle: "short"}).format(new Date(value));
    } catch (_) {
      return value;
    }
  };

  const loadNotifications = async () => {
    if (!notificationPreview) return;
    notificationPreview.innerHTML = '<p class="muted">Carregando...</p>';
    try {
      const response = await fetch("/api/notifications");
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Falha ao carregar notificações.");
      if (notificationBadge) {
        notificationBadge.textContent = payload.unread;
        notificationBadge.hidden = payload.unread === 0;
      }
      notificationPreview.innerHTML = payload.items.length ? payload.items.map(item => `
        <a class="notification-preview-item ${item.is_read ? "" : "is-unread"}" href="${item.link}">
          <i class="notification-kind notification-kind--${item.category}"></i>
          <span><strong>${item.title}</strong><small>${item.message}</small><time>${formatDate(item.created_at)}</time></span>
        </a>`).join("") : '<p class="muted">Nenhuma notificação disponível.</p>';
    } catch (error) {
      notificationPreview.innerHTML = `<p class="muted">${error.message}</p>`;
    }
  };

  notificationButton?.addEventListener("click", event => {
    event.stopPropagation();
    const opening = notificationPopover?.hidden;
    togglePopover(notificationButton, notificationPopover);
    if (opening) loadNotifications();
  });

  document.addEventListener("click", event => {
    if (!event.target.closest(".topbar-popover-wrap")) closePopovers();
  });

  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      globalSearch?.focus();
      globalSearch?.select();
    }
    if (event.key === "Escape") {
      closeMobileMenu();
      closePopovers();
    }
  });

  const params = new URLSearchParams(window.location.search);
  const message = params.get("message");
  if (message) {
    const toast = document.querySelector("#toast");
    if (toast) {
      toast.textContent = message;
      toast.className = `toast is-visible${params.get("kind") === "error" ? " is-error" : ""}`;
      setTimeout(() => { toast.className = "toast"; }, 4500);
    }
  }
})();
