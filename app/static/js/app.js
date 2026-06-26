(() => {
  "use strict";

  const permissionCatalog = [
    ["VIEW", "Visualizar"],
    ["REGISTER", "Registrar"],
    ["EDIT", "Editar"],
    ["DELETE", "Excluir"],
    ["MONITOR", "Monitorar"],
    ["APPROVE", "Aprovar"],
    ["ADMINISTER", "Administrar"]
  ];
  const permissionLabels = Object.fromEntries(permissionCatalog);
  const statusLabels = {
    draft: "Rascunho",
    pending_approval: "Pendente de aprovação",
    approved: "Aprovado",
    synced: "Sincronizado"
  };
  const auditLabels = {
    seed_created: "Base inicial criada",
    process_created: "Processo criado",
    matrix_saved: "Matriz de permissões atualizada",
    submitted_for_approval: "Processo enviado para aprovação",
    approval_stage_completed: "Etapa de aprovação concluída",
    approved: "Versão aprovada",
    rejected: "Processo devolvido para ajustes",
    reopened: "Processo reaberto para edição",
    n8n_callback: "Retorno recebido do n8n",
    bizagi_simulated: "Integração com Bizagi simulada",
    bizagi_synced: "Integração com Bizagi concluída",
    bizagi_sync_failed: "Falha na integração com Bizagi"
  };

  const qs = selector => document.querySelector(selector);
  const qsa = selector => [...document.querySelectorAll(selector)];
  const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
  const normalizeSearch = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR").trim();

  const toast = qs("#toast");
  const matrixBody = qs("#matrixBody");
  const profileFilter = qs("#profileFilter");
  const profileDialog = qs("#profileDialog");
  const profileForm = qs("#profileForm");

  const initialDataElement = qs("#initialData");
  const runtimeConfigElement = qs("#processRuntimeConfig");
  const initialData = initialDataElement ? JSON.parse(initialDataElement.textContent || "{}") : {};
  const runtimeFlag = name => runtimeConfigElement?.dataset[name] === "true";
  const bizagiEnabled = runtimeFlag("bizagiEnabled");
  const canEdit = runtimeFlag("canEdit");
  const canSubmit = runtimeFlag("canSubmit");
  const canApprove = runtimeFlag("canApprove");
  const canReopen = runtimeFlag("canReopen");
  const canIntegrate = runtimeFlag("canIntegrate");
  const canExport = runtimeFlag("canExport");
  let processState = structuredClone(initialData);
  let profiles = (processState.profiles || []).map(normalizeProfile);
  let selectedProfileIndex = null;
  let editingProfileIndex = null;
  let dirty = false;
  let payloadCache = "";

  function showToast(message, error = false) {
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast is-visible${error ? " is-error" : ""}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => { toast.className = "toast"; }, 3600);
  }

  function normalizeProfile(profile) {
    return {
      hierarchy: profile.hierarchy || "",
      profile_name: profile.profile_name || "",
      agent_type: profile.agent_type || "Não se aplica",
      permission_summary: profile.permission_summary || "Não se aplica",
      source_reference: profile.source_reference || "Cadastro manual",
      notes: profile.notes || "",
      permissions: applyDependencies(profile.permissions || [])
    };
  }

  function applyDependencies(codes) {
    const result = new Set(codes.filter(code => permissionLabels[code]));
    if (["REGISTER", "EDIT", "DELETE", "MONITOR", "APPROVE", "ADMINISTER"].some(code => result.has(code))) result.add("VIEW");
    if (result.has("APPROVE")) result.add("MONITOR");
    if (result.has("ADMINISTER")) permissionCatalog.forEach(([code]) => result.add(code));
    return permissionCatalog.map(([code]) => code).filter(code => result.has(code));
  }

  function getPermissionSummary(codes) {
    const normalized = applyDependencies(codes);
    return normalized.length ? normalized.map(code => permissionLabels[code]).join(", ") : "Não se aplica";
  }

  function isDerivedPermission(profile, code) {
    if (!profile.permissions.includes(code)) return false;
    if (profile.permissions.includes("ADMINISTER") && code !== "ADMINISTER") return true;
    if (code === "VIEW" && profile.permissions.some(item => ["REGISTER", "EDIT", "DELETE", "MONITOR", "APPROVE", "ADMINISTER"].includes(item))) return true;
    if (code === "MONITOR" && profile.permissions.includes("APPROVE")) return true;
    return false;
  }

  function setDirty(value = true) {
    dirty = value;
    const indicator = qs("#dirtyIndicator");
    if (indicator) {
      indicator.textContent = value ? "Alterações não salvas" : "Sem alterações pendentes";
      indicator.classList.toggle("is-dirty", value);
    }
  }

  function initials(value) {
    const words = String(value || "Perfil").trim().split(/\s+/).filter(Boolean);
    return words.slice(0, 2).map(word => word[0]).join("").toUpperCase();
  }

  function refreshProfileFilter(preferred = null) {
    const current = preferred ?? profileFilter.value ?? "all";
    const grouped = new Map();
    profiles.forEach((profile, index) => {
      const hierarchy = profile.hierarchy.trim() || "Sem hierarquia";
      if (!grouped.has(hierarchy)) grouped.set(hierarchy, []);
      grouped.get(hierarchy).push({profile, index});
    });

    let html = `<option value="all">Todos os perfis (${profiles.length})</option>`;
    [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b, "pt-BR")).forEach(([hierarchy, items]) => {
      html += `<optgroup label="${escapeHtml(hierarchy)}">`;
      items.sort((a, b) => a.profile.profile_name.localeCompare(b.profile.profile_name, "pt-BR")).forEach(({profile, index}) => {
        html += `<option value="${index}">${escapeHtml(profile.profile_name || `Perfil ${index + 1}`)}</option>`;
      });
      html += "</optgroup>";
    });
    profileFilter.innerHTML = html;
    profileFilter.value = current === "all" || profiles[Number(current)] ? current : "all";
  }

  function updateSelectionControls() {
    const selected = Number.isInteger(selectedProfileIndex) && profiles[selectedProfileIndex];
    const locked = processState.status !== "draft" || !canEdit;
    qs("#duplicateProfileButton").disabled = !selected || locked;
    qs("#deleteProfileButton").disabled = !selected || locked;
  }

  function renderMatrix() {
    const filterValue = profileFilter.value || "all";
    const locked = processState.status !== "draft" || !canEdit;
    let visibleCount = 0;

    if (!profiles.length) {
      matrixBody.innerHTML = `<tr><td colspan="11"><div class="empty-state"><strong>Nenhum perfil cadastrado.</strong><span>Use “Adicionar perfil” para iniciar a matriz.</span></div></td></tr>`;
      qs("#matrixVisibleCount").textContent = "0";
      updateSelectionControls();
      return;
    }

    matrixBody.innerHTML = profiles.map((profile, index) => {
      const visible = filterValue === "all" || Number(filterValue) === index;
      if (visible) visibleCount += 1;
      const selectedClass = selectedProfileIndex === index ? "is-selected" : "";
      const permissionCells = permissionCatalog.map(([code, label]) => {
        const checked = profile.permissions.includes(code);
        const derived = isDerivedPermission(profile, code);
        return `<td class="permission-cell">
          <label class="permission-toggle${derived ? " is-derived" : ""}" title="${derived ? "Concedida automaticamente por dependência de outra permissão." : label}">
            <input type="checkbox" data-index="${index}" data-permission="${code}" ${checked ? "checked" : ""} ${locked ? "disabled" : ""}>
            <span aria-hidden="true"></span>
          </label>
        </td>`;
      }).join("");

      return `<tr data-row-index="${index}" class="${selectedClass}" ${visible ? "" : "hidden"}>
        <td>${escapeHtml(profile.hierarchy || "—")}</td>
        <td><button class="profile-cell-button" type="button" data-edit-profile="${index}" title="Editar dados do perfil"><span class="profile-badge profile-badge--${index % 8}">${escapeHtml(initials(profile.profile_name))}</span>${escapeHtml(profile.profile_name || "Perfil sem nome")}</button></td>
        <td>${escapeHtml(profile.agent_type || "Não se aplica")}</td>
        ${permissionCells}
        <td><button class="row-action-button" type="button" data-edit-profile="${index}" title="Editar perfil"><svg><use href="#i-more"/></svg></button></td>
      </tr>`;
    }).join("");

    qs("#matrixVisibleCount").textContent = String(visibleCount);
    updateSelectionControls();
  }

  function renderPermissionPicker(codes = []) {
    const selected = new Set(codes);
    qs("#profilePermissionPicker").innerHTML = permissionCatalog.map(([code, label]) => `
      <label><input type="checkbox" value="${code}" ${selected.has(code) ? "checked" : ""}><span>${escapeHtml(label)}</span></label>
    `).join("");
  }

  function openProfileDialog(index = null) {
    if (processState.status !== "draft" || !canEdit) {
      showToast(canEdit ? "A matriz está bloqueada. Reabra o processo para editar perfis." : "Seu papel não permite editar perfis.", true);
      return;
    }
    editingProfileIndex = Number.isInteger(index) ? index : null;
    const profile = editingProfileIndex === null ? normalizeProfile({}) : profiles[editingProfileIndex];
    qs("#profileDialogEyebrow").textContent = editingProfileIndex === null ? "NOVO PERFIL" : "EDITAR PERFIL";
    qs("#profileDialogTitle").textContent = editingProfileIndex === null ? "Cadastrar perfil" : profile.profile_name;
    qs("#profileHierarchy").value = profile.hierarchy;
    qs("#profileName").value = profile.profile_name;
    qs("#profileAgentType").value = profile.agent_type;
    qs("#profileSourceReference").value = profile.source_reference;
    qs("#profileNotes").value = profile.notes;
    qs("#profileFormError").hidden = true;
    renderPermissionPicker(profile.permissions);
    profileDialog.showModal();
    setTimeout(() => qs("#profileHierarchy").focus(), 30);
  }

  function closeProfileDialog() {
    profileDialog.close();
    profileForm.reset();
    editingProfileIndex = null;
  }

  function selectProfile(index) {
    selectedProfileIndex = Number.isInteger(index) && profiles[index] ? index : null;
    if (selectedProfileIndex !== null && profileFilter.value !== "all" && Number(profileFilter.value) !== selectedProfileIndex) {
      profileFilter.value = String(selectedProfileIndex);
    }
    renderMatrix();
  }

  function validateMatrix(show = true) {
    const errors = [];
    if (!qs("#processCode").value.trim()) errors.push("Informe o código do processo.");
    if (!qs("#processName").value.trim()) errors.push("Informe o nome do processo.");
    if (!qs("#processResponsible").value.trim()) errors.push("Informe o responsável pelo processo.");
    if (!qs("#processArea").value.trim()) errors.push("Informe a área do processo.");
    if (!profiles.length) errors.push("Inclua pelo menos um perfil.");

    const keys = new Set();
    profiles.forEach((profile, index) => {
      if (!profile.hierarchy.trim()) errors.push(`Perfil ${index + 1}: informe a hierarquia.`);
      if (!profile.profile_name.trim()) errors.push(`Perfil ${index + 1}: informe o nome.`);
      const key = `${normalizeSearch(profile.hierarchy)}|${normalizeSearch(profile.profile_name)}`;
      if (keys.has(key)) errors.push(`Perfil ${index + 1}: hierarquia e nome duplicados.`);
      keys.add(key);
    });

    const box = qs("#matrixValidation");
    box.hidden = !show || errors.length === 0;
    box.innerHTML = errors.length ? `<strong>Revise os seguintes pontos:</strong><ul>${errors.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "";
    return errors;
  }

  function updateCounters() {
    qs("#processNameCounter").textContent = `${qs("#processName").value.length} / 250`;
    qs("#descriptionCounter").textContent = `${qs("#processDescription").value.length} / 5000`;
  }

  function updateHeaderPreview() {
    const code = qs("#processCode").value.trim() || "SEM-CÓDIGO";
    const name = qs("#processName").value.trim() || "Processo sem nome";
    const responsible = qs("#processResponsible").value.trim() || "Não informado";
    qs("#titleboardCode").textContent = code;
    qs("#breadcrumbCode").textContent = code;
    qs("#pageTitle").textContent = name;
    qs("#summaryResponsible").textContent = responsible;
    updateCounters();
  }

  function populateProcessFields() {
    qs("#processCode").value = processState.code || "";
    qs("#processName").value = processState.name || "";
    qs("#processResponsible").value = processState.responsible || "";
    qs("#processArea").value = processState.area || "";
    qs("#processDescription").value = processState.description || "";
    qs("#processSourceDocument").value = processState.source_document || "";
    updateHeaderPreview();
    setDirty(false);
  }

  function updateApprovalDestination() {
    const destination = qs("#approvalDestination");
    const current = processState.current_approval;
    if (!destination) return;
    destination.hidden = !current;
    if (!current) return;
    qs("#approvalDestinationStage").textContent = current.stage_name || "Etapa de aprovação";
    qs("#approvalDestinationAssignee").textContent = `Responsável: ${current.assigned_to || "Não informado"}`;

    const items = qsa("#approvalFlow li");
    if (items[1]) {
      items[1].querySelector("span").textContent = current.stage_order === 1 ? current.assigned_to : "Concluída";
      items[1].querySelector("small").textContent = current.stage_order === 1 ? "Aguardando decisão" : "Revisão concluída";
    }
    if (items[2]) {
      items[2].querySelector("span").textContent = current.stage_order === 2 ? current.assigned_to : "Aprovador final";
      items[2].querySelector("small").textContent = current.stage_order === 2 ? "Aguardando decisão" : "Próxima etapa";
    }
  }

  function updateStatus() {
    const status = processState.status || "draft";
    const locked = status !== "draft" || !canEdit;
    const badge = qs("#statusBadge");
    badge.className = `status-label status-label--${status}`;
    badge.innerHTML = `<i></i>${escapeHtml(statusLabels[status] || status)}`;
    qs("#versionBadge").textContent = `Versão ${processState.version}`;
    qs("#workflowCode").textContent = status;

    ["#processCode", "#processName", "#processResponsible", "#processArea", "#processDescription", "#processSourceDocument"].forEach(selector => {
      qs(selector).disabled = locked;
    });
    qs("#clearDocumentButton").disabled = locked;
    qs("#saveButton").disabled = locked;
    qs("#submitButton").disabled = status !== "draft" || !canSubmit;
    qs("#addProfileButton").disabled = locked;
    qs("#approveButton").disabled = status !== "pending_approval" || !canApprove;
    qs("#rejectButton").disabled = status !== "pending_approval" || !canApprove;
    qs("#reopenButton").disabled = status === "draft" || !canReopen;
    qs("#simulateButton").disabled = status !== "approved" || !canIntegrate;
    qs("#syncButton").disabled = status !== "approved" || !bizagiEnabled || !canIntegrate;
    qsa("[data-export]").forEach(button => { button.disabled = !canExport; });

    const order = ["draft", "pending_approval", "approved", "synced"];
    const currentIndex = order.indexOf(status);
    qsa("#approvalFlow li").forEach((item, index) => {
      item.classList.toggle("is-complete", index < currentIndex || status === "synced");
      item.classList.toggle("is-current", index === currentIndex);
    });
    updateApprovalDestination();
    updateSelectionControls();
    renderMatrix();
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("pt-BR", {dateStyle: "short", timeStyle: "short"}).format(date);
  }

  function renderAudit() {
    const events = processState.audit_events || [];
    qs("#auditMetric").textContent = String(events.length);
    qs("#auditTimeline").innerHTML = events.length ? events.slice(0, 7).map(event => {
      const color = event.action.includes("bizagi") ? "is-blue" : event.action === "submitted_for_approval" ? "is-amber" : ["approved", "matrix_saved"].includes(event.action) ? "is-green" : "";
      return `<article class="audit-event"><span class="audit-event-icon ${color}">${escapeHtml(initials(event.actor))}</span><div><strong>${escapeHtml(event.actor || "Sistema")}</strong><span>${escapeHtml(auditLabels[event.action] || event.action)}</span><time>${escapeHtml(formatDate(event.created_at))}</time></div></article>`;
    }).join("") : `<div class="rail-empty">Nenhum evento registrado.</div>`;
  }

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {"Content-Type": "application/json", ...(options.headers || {})}
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || body.message || `Erro HTTP ${response.status}`);
    return body;
  }

  function actorPayload() {
    return {actor: qs("#actor").value.trim() || "Usuário local"};
  }

  async function saveMatrix() {
    if (validateMatrix(true).length) {
      qs("#matrixPanel").scrollIntoView({behavior: "smooth", block: "start"});
      return false;
    }
    const payload = {
      code: qs("#processCode").value.trim(),
      name: qs("#processName").value.trim(),
      responsible: qs("#processResponsible").value.trim(),
      area: qs("#processArea").value.trim(),
      description: qs("#processDescription").value.trim(),
      source_document: qs("#processSourceDocument").value.trim(),
      actor: actorPayload().actor,
      row_version: processState.row_version || null,
      profiles: profiles.map(profile => ({...profile, permission_summary: getPermissionSummary(profile.permissions)}))
    };

    try {
      const result = await request(`/api/processes/${processState.id}/matrix`, {method: "PUT", body: JSON.stringify(payload)});
      processState = result.process;
      profiles = (processState.profiles || []).map(normalizeProfile);
      refreshProfileFilter("all");
      selectedProfileIndex = null;
      populateProcessFields();
      updateStatus();
      renderAudit();
      qs("#summaryUpdatedAt").textContent = formatDate(processState.updated_at);
      showToast(result.warnings?.length ? `Salvo com ${result.warnings.length} alerta(s).` : result.message);
      return true;
    } catch (error) {
      showToast(error.message, true);
      return false;
    }
  }

  async function workflowAction(action, note = "") {
    try {
      const payload = {...actorPayload(), note};
      const result = await request(`/api/processes/${processState.id}/${action}`, {method: "POST", body: JSON.stringify(payload)});
      processState = result.process;
      profiles = (processState.profiles || []).map(normalizeProfile);
      populateProcessFields();
      updateStatus();
      renderAudit();
      showToast(result.message);
    } catch (error) {
      showToast(error.message, true);
    }
  }

  async function showPayload() {
    try {
      const payload = await request(`/api/processes/${processState.id}/bizagi/payload`);
      payloadCache = JSON.stringify(payload, null, 2);
      qs("#payloadPreview").textContent = payloadCache;
      qs("#payloadDialog").showModal();
    } catch (error) {
      showToast(error.message, true);
    }
  }

  async function integrationAction(action) {
    try {
      const result = await request(`/api/processes/${processState.id}/bizagi/${action}`, {method: "POST", body: JSON.stringify(actorPayload())});
      showToast(result.message);
      processState = await request(`/api/processes/${processState.id}`);
      profiles = (processState.profiles || []).map(normalizeProfile);
      updateStatus();
      renderAudit();
    } catch (error) {
      showToast(error.message, true);
    }
  }

  profileFilter.addEventListener("change", () => {
    selectedProfileIndex = profileFilter.value === "all" ? null : Number(profileFilter.value);
    renderMatrix();
  });

  matrixBody.addEventListener("click", event => {
    const editButton = event.target.closest("[data-edit-profile]");
    if (editButton) {
      const index = Number(editButton.dataset.editProfile);
      selectProfile(index);
      openProfileDialog(index);
      return;
    }
    const row = event.target.closest("tr[data-row-index]");
    if (row) selectProfile(Number(row.dataset.rowIndex));
  });

  matrixBody.addEventListener("change", event => {
    const input = event.target.closest("input[data-permission]");
    if (!input) return;
    const index = Number(input.dataset.index);
    const code = input.dataset.permission;
    const set = new Set(profiles[index].permissions);
    input.checked ? set.add(code) : set.delete(code);
    profiles[index].permissions = applyDependencies([...set]);
    selectedProfileIndex = index;
    setDirty();
    renderMatrix();
  });

  qs("#addProfileButton").addEventListener("click", () => openProfileDialog());
  qs("#duplicateProfileButton").addEventListener("click", () => {
    if (selectedProfileIndex === null || !profiles[selectedProfileIndex]) return;
    const copy = structuredClone(profiles[selectedProfileIndex]);
    copy.profile_name = `${copy.profile_name} - cópia`;
    profiles.splice(selectedProfileIndex + 1, 0, copy);
    selectedProfileIndex += 1;
    refreshProfileFilter(String(selectedProfileIndex));
    setDirty();
    renderMatrix();
    showToast("Perfil duplicado. Salve o rascunho para confirmar.");
  });
  qs("#deleteProfileButton").addEventListener("click", () => {
    if (selectedProfileIndex === null || !profiles[selectedProfileIndex]) return;
    const name = profiles[selectedProfileIndex].profile_name;
    if (!window.confirm(`Excluir o perfil “${name}” da matriz?`)) return;
    profiles.splice(selectedProfileIndex, 1);
    selectedProfileIndex = null;
    refreshProfileFilter("all");
    setDirty();
    renderMatrix();
  });

  profileForm.addEventListener("submit", event => {
    event.preventDefault();
    const hierarchy = qs("#profileHierarchy").value.trim();
    const profileName = qs("#profileName").value.trim();
    const errorBox = qs("#profileFormError");
    if (!hierarchy || !profileName) {
      errorBox.textContent = "Informe a hierarquia e o nome do perfil.";
      errorBox.hidden = false;
      return;
    }
    const permissions = qsa("#profilePermissionPicker input:checked").map(input => input.value);
    const profile = normalizeProfile({
      hierarchy,
      profile_name: profileName,
      agent_type: qs("#profileAgentType").value.trim() || "Não se aplica",
      source_reference: qs("#profileSourceReference").value.trim() || "Cadastro manual",
      notes: qs("#profileNotes").value.trim(),
      permissions
    });
    if (editingProfileIndex === null) {
      profiles.push(profile);
      selectedProfileIndex = profiles.length - 1;
    } else {
      profiles[editingProfileIndex] = profile;
      selectedProfileIndex = editingProfileIndex;
    }
    refreshProfileFilter(String(selectedProfileIndex));
    setDirty();
    renderMatrix();
    closeProfileDialog();
  });

  qs("#closeProfileDialog").addEventListener("click", closeProfileDialog);
  qs("#cancelProfileDialog").addEventListener("click", closeProfileDialog);
  profileDialog.addEventListener("click", event => { if (event.target === profileDialog) closeProfileDialog(); });

  ["#processCode", "#processName", "#processResponsible", "#processArea", "#processDescription", "#processSourceDocument"].forEach(selector => {
    qs(selector).addEventListener("input", () => {
      setDirty();
      updateHeaderPreview();
    });
  });
  qs("#clearDocumentButton").addEventListener("click", () => {
    qs("#processSourceDocument").value = "";
    setDirty();
  });
  qs("#copyProcessCode").addEventListener("click", async () => {
    await navigator.clipboard.writeText(qs("#processCode").value.trim());
    showToast("Código copiado para a área de transferência.");
  });

  qs("#saveButton").addEventListener("click", saveMatrix);
  qs("#submitButton").addEventListener("click", async () => { if (await saveMatrix()) await workflowAction("submit"); });
  qs("#approveButton").addEventListener("click", () => workflowAction("approve"));
  qs("#rejectButton").addEventListener("click", () => {
    const note = window.prompt("Descreva os ajustes necessários para devolver o processo:", "");
    if (note === null) return;
    workflowAction("reject", note.trim());
  });
  qs("#reopenButton").addEventListener("click", () => workflowAction("reopen"));
  qs("#payloadButton").addEventListener("click", showPayload);
  qs("#simulateButton").addEventListener("click", () => integrationAction("simulate"));
  qs("#syncButton").addEventListener("click", () => integrationAction("sync"));

  const moreButton = qs("#processMoreButton");
  const moreMenu = qs("#processMoreMenu");
  moreButton.addEventListener("click", event => {
    event.stopPropagation();
    moreMenu.hidden = !moreMenu.hidden;
  });
  document.addEventListener("click", event => {
    if (!event.target.closest(".action-menu-wrap")) moreMenu.hidden = true;
  });

  qsa(".section-tabs [data-scroll-target]").forEach(button => button.addEventListener("click", () => {
    qsa(".section-tabs button").forEach(item => item.classList.toggle("is-active", item === button));
    document.getElementById(button.dataset.scrollTarget)?.scrollIntoView({behavior: "smooth", block: "start"});
  }));

  qs("#closePayloadButton").addEventListener("click", () => qs("#payloadDialog").close());
  qs("#copyPayloadButton").addEventListener("click", async () => {
    await navigator.clipboard.writeText(payloadCache);
    showToast("JSON copiado para a área de transferência.");
  });
  qsa("[data-export]").forEach(button => button.addEventListener("click", () => {
    window.location.href = `/api/processes/${processState.id}/export/${button.dataset.export}`;
  }));

  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (!qs("#saveButton").disabled) saveMatrix();
    }
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      profileFilter.focus();
    }
  });

  window.addEventListener("beforeunload", event => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  populateProcessFields();
  refreshProfileFilter("all");
  renderMatrix();
  renderAudit();
  updateStatus();
})();
