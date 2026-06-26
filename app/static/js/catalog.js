(() => {
  const normalize = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  const search = document.querySelector("#catalogSearch") || document.querySelector("#processSearch");
  const status = document.querySelector("#statusFilter");
  const rows = [...document.querySelectorAll("tbody tr[data-search], .process-registry-row")];
  const empty = document.querySelector("#processNoResults");

  const apply = () => {
    const term = normalize(search?.value);
    const statusValue = status?.value || "all";
    let visible = 0;
    rows.forEach(row => {
      const matchesTerm = !term || normalize(row.dataset.search).includes(term);
      const matchesStatus = statusValue === "all" || row.dataset.status === statusValue;
      row.hidden = !(matchesTerm && matchesStatus);
      if (!row.hidden) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  };

  search?.addEventListener("input", apply);
  status?.addEventListener("change", apply);

  document.querySelectorAll("[data-open-dialog]").forEach(button => {
    button.addEventListener("click", () => document.getElementById(button.dataset.openDialog)?.showModal());
  });
  document.querySelectorAll("[data-close-dialog]").forEach(button => {
    button.addEventListener("click", () => document.getElementById(button.dataset.closeDialog)?.close());
  });
  document.querySelectorAll("dialog").forEach(dialog => {
    dialog.addEventListener("click", event => {
      if (event.target === dialog) dialog.close();
    });
  });

  const params = new URLSearchParams(window.location.search);
  if (params.get("query") && search) {
    search.value = params.get("query");
  }
  apply();
})();
