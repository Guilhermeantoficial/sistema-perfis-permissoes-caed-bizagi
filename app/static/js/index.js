(() => {
  const dialog = document.querySelector("#newProcessDialog");
  const form = document.querySelector("#newProcessForm");
  const errorBox = document.querySelector("#newProcessError");
  const toast = document.querySelector("#toast");
  const processRows = [...document.querySelectorAll(".process-registry-row")];
  const searchInput = document.querySelector("#processSearch");
  const statusFilter = document.querySelector("#statusFilter");
  const visibleCounter = document.querySelector("#visibleProcessCount");
  const noResults = document.querySelector("#processNoResults");

  const normalize = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

  const showToast = (message, error = false) => {
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast is-visible${error ? " is-error" : ""}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => { toast.className = "toast"; }, 3600);
  };

  const openDialog = () => {
    errorBox.hidden = true;
    errorBox.textContent = "";
    dialog.showModal();
    setTimeout(() => document.querySelector("#newProcessCode")?.focus(), 50);
  };

  const closeDialog = () => {
    dialog.close();
    form.reset();
  };

  const filterProcesses = () => {
    const term = normalize(searchInput?.value);
    const status = statusFilter?.value || "all";
    let visible = 0;
    processRows.forEach(row => {
      const matchesTerm = !term || normalize(row.dataset.search).includes(term);
      const matchesStatus = status === "all" || row.dataset.status === status;
      row.hidden = !(matchesTerm && matchesStatus);
      if (!row.hidden) visible += 1;
    });
    if (visibleCounter) visibleCounter.textContent = visible;
    if (noResults) noResults.hidden = visible > 0;
  };

  document.querySelector("#newProcessButton")?.addEventListener("click", openDialog);
  document.querySelector("#closeProcessDialog")?.addEventListener("click", closeDialog);
  document.querySelector("#cancelProcessButton")?.addEventListener("click", closeDialog);
  searchInput?.addEventListener("input", filterProcesses);
  statusFilter?.addEventListener("change", filterProcesses);
  dialog?.addEventListener("click", event => { if (event.target === dialog) closeDialog(); });

  form?.addEventListener("submit", async event => {
    event.preventDefault();
    const payload = {
      code: document.querySelector("#newProcessCode").value.trim(),
      name: document.querySelector("#newProcessName").value.trim(),
      responsible: document.querySelector("#newProcessResponsible").value.trim(),
      area: document.querySelector("#newProcessArea").value.trim(),
      source_document: document.querySelector("#newProcessSource").value.trim(),
      description: document.querySelector("#newProcessDescription").value.trim(),
      actor: "Guilherme Rodrigues"
    };

    if (!payload.code || !payload.name) {
      errorBox.textContent = "Informe o código e o nome do processo.";
      errorBox.hidden = false;
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    const original = submitButton.innerHTML;
    submitButton.disabled = true;
    submitButton.textContent = "Criando...";

    try {
      const response = await fetch("/api/processes", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || body.message || `Erro HTTP ${response.status}`);
      showToast(body.message);
      window.location.href = `/processes/${body.process.id}`;
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
      showToast(error.message, true);
    } finally {
      submitButton.disabled = false;
      submitButton.innerHTML = original;
    }
  });

  if (window.location.hash === "#new") openDialog();
  filterProcesses();
})();
