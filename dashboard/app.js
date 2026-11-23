import { money, negative, validPeriod, dateLabel } from './format.mjs';
import { orderedRoles, groupedPermissions, isReadOnlyRole } from './matrix.mjs';

const $ = id => document.getElementById(id);
const KEY = 'sgi-session';
const fields = ['openingBalance', 'totalIncome', 'totalExpense', 'profit', 'closingBalance'];
const ACCOUNT_LABELS = {
  CASH: 'Efectivo', DEBIT: 'Débito', CREDIT: 'Crédito', SAVINGS: 'Ahorro',
  INVESTMENT: 'Inversión', WALLET: 'Monedero', OTHER: 'Otro',
};
const CONCEPT_LABELS = { INCOME: 'Ingreso', EXPENSE: 'Egreso' };

const LOGIN = `mutation IniciarSesion($input: LoginInput!) { login(input: $input) { token tokenType user { name } } }`;
const ME = `query { me { companyUserId companyId companyName isAdmin user { name email } role { code name } permissions } }`;
const BALANCE = `query IndicadoresEmpresa($from: Date!, $to: Date!) {
  generalBalance(fromDate: $from, toDate: $to) {
    companyId companyName currency fromDate toDate openingBalance totalIncome totalExpense
    profit closingBalance isInRed accountsInRed transactionCount
    accounts { accountId accountName isActive openingBalance totalIncome totalExpense profit closingBalance isInRed transactionCount }
  }
}`;
const COMPANY_USERS = `query { companyUsers { id isAdmin isActive user { name email } role { id code name } } }`;
const ACCOUNTS = `query { accounts { id name accountType bankName cardLastDigits clabe isActive } }`;
const CONCEPTS = `query { concepts { id name conceptType isActive shortDescription } }`;
const ACCOUNT_CONCEPTS = `query($accountId: ID!) { accountConcepts(accountId: $accountId) { id isActive concept { id name conceptType } } }`;
const ACTIVE_ROLES = `query { roles(activeOnly: true) { id code name } }`;
const MATRIX_CATALOG = `query Matriz {
  roles(activeOnly: true) { id code name }
  permissions(activeOnly: true) { id code name }
}`;
const ROLE_PERMISSIONS = `query ListaDelRol($roleId: ID!) {
  rolePermissions(roleId: $roleId) {
    isActive
    permission { id code }
  }
}`;
const PREVIEW_ROLE_PERMISSIONS = `query VistaPrevia($input: SetRolePermissionsInput!) {
  previewRolePermissions(input: $input) {
    toActivate { code }
    toDeactivate { code }
    unchanged { code }
    finalCount
  }
}`;
const SET_ROLE_PERMISSIONS = `mutation GuardarColumna($input: SetRolePermissionsInput!) {
  setRolePermissions(input: $input) {
    activated { code }
    deactivated { code }
    finalCount
    changed
  }
}`;
const ASSIGN_ROLE = `mutation AsignarPuesto($input: AssignRoleInput!) {
  assignRole(input: $input) {
    isActive
    role { id code name }
  }
}`;

let session = null;
let pending = null;
let requestId = 0;
let currentView = 'financial';
let currentAdmin = 'users';
let usersCache = [];
let accountsCache = [];
let conceptsCache = [];
let assignmentsCache = [];
let rolesCache = [];
let permissionsCache = [];
let matrixSaved = new Map();
let matrixDraft = new Map();
let activePreview = null;

function notice(id, message, neutral = false) {
  const node = $(id);
  node.textContent = message;
  node.hidden = !message;
  node.classList.toggle('neutral', neutral);
}

function clearResults() {
  $('results').hidden = true;
  fields.forEach(field => $(field).textContent = '');
  $('account-rows').replaceChildren();
  $('applied-period').textContent = '';
}

function saveSession(value) {
  session = value;
  try {
    value ? sessionStorage.setItem(KEY, JSON.stringify(value)) : sessionStorage.removeItem(KEY);
  } catch { /* Memoria si el navegador bloquea almacenamiento. */ }
}

function can(permission) {
  return Boolean(session?.permissions?.includes(permission));
}

function logout(message = '') {
  pending?.abort();
  requestId++;
  saveSession(null);
  clearResults();
  rolesCache = [];
  permissionsCache = [];
  matrixSaved = new Map();
  matrixDraft = new Map();
  activePreview = null;
  $('matrix-preview').hidden = true;
  defaultPeriod();
  $('app-view').hidden = true;
  $('login-view').hidden = false;
  $('password').value = '';
  $('user-name').textContent = '';
  $('company-label').textContent = '';
  $('company').textContent = 'Consulta el balance de tu empresa.';
  notice('status', '');
  notice('admin-status', '');
  notice('login-message', message);
  $('email').focus();
}

async function graphql(query, variables, token, signal) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch('/graphql', {
      method: 'POST',
      headers,
      body: JSON.stringify({ query, variables }),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('No pudimos conectar con el servidor. Revisa que el API esté iniciado e intenta de nuevo.');
  }
  if (response.status === 401) {
    throw Object.assign(new Error('Tu sesión venció. Inicia sesión nuevamente.'), { code: 'UNAUTHENTICATED' });
  }
  if (!response.ok) throw new Error('El servidor no pudo completar la consulta. Intenta nuevamente.');
  const result = await response.json();
  if (result.errors?.length) {
    const error = result.errors[0];
    const code = error.extensions?.code;
    const known = ['UNAUTHENTICATED', 'FORBIDDEN', 'BAD_USER_INPUT', 'NOT_FOUND'].includes(code);
    const loginError = !token && /correo|contraseña|membresía/i.test(error.message);
    throw Object.assign(
      new Error(known || loginError || Boolean(token) ? error.message : 'No fue posible obtener la información. Intenta de nuevo.'),
      { code },
    );
  }
  if (!result.data) throw new Error('El servidor no devolvió datos. Intenta nuevamente.');
  return result.data;
}

function maskReference(account) {
  if (account.cardLastDigits) return `****${account.cardLastDigits}`;
  if (account.clabe && account.clabe.length >= 4) {
    return `${'*'.repeat(Math.max(account.clabe.length - 4, 0))}${account.clabe.slice(-4)}`;
  }
  return '—';
}

function badge(label, className = '') {
  const span = document.createElement('span');
  span.className = `badge ${className}`.trim();
  span.textContent = label;
  return span;
}

function setView(view) {
  currentView = view;
  $('financial-view').hidden = view !== 'financial';
  $('admin-view').hidden = view !== 'admin';
  $('admin-subnav').hidden = view !== 'admin';
  document.querySelectorAll('.nav-item').forEach(node => {
    node.classList.toggle('active', node.dataset.view === view);
  });
  if (view === 'financial') loadBalance();
  else setAdminPanel(currentAdmin);
}

function allowedAdminPanels() {
  const panels = [];
  if (can('company.users.read')) panels.push('users');
  if (can('accounts.read')) panels.push('accounts');
  if (can('concepts.read')) panels.push('concepts');
  if (can('roles.read')) panels.push('roles');
  return panels;
}

function setAdminPanel(panel) {
  const allowed = allowedAdminPanels();
  if (!allowed.includes(panel)) panel = allowed[0] || 'users';
  currentAdmin = panel;
  document.querySelectorAll('.subnav-item').forEach(node => {
    node.classList.toggle('active', node.dataset.admin === panel);
  });
  $('users-panel').hidden = panel !== 'users';
  $('accounts-panel').hidden = panel !== 'accounts';
  $('concepts-panel').hidden = panel !== 'concepts';
  $('roles-panel').hidden = panel !== 'roles';
  const sessionSuffix = session?.user?.name
    ? ` Sesión de ${session.user.name}${session.role?.name ? ` · ${session.role.name}` : ''}.`
    : '';
  const titles = {
    users: ['Usuarios', 'Membresías de la empresa autenticada.'],
    accounts: ['Cuentas', 'Dónde se guarda el dinero de la empresa.'],
    concepts: ['Conceptos', 'Por qué entra o sale el dinero y qué se permite en cada cuenta.'],
    roles: ['Roles y permisos', `Catálogo compartido. Un cambio en el puesto vale para todas las empresas.${sessionSuffix}`],
  };
  $('admin-title').textContent = titles[panel][0];
  $('admin-subtitle').textContent = titles[panel][1];
  notice('admin-status', '');
  if (panel === 'users') loadUsers();
  if (panel === 'accounts') loadAccounts();
  if (panel === 'concepts') loadConcepts();
  if (panel === 'roles') loadRolesMatrix();
}

async function showApp() {
  $('login-view').hidden = true;
  $('app-view').hidden = false;
  $('user-name').textContent = session.user?.name || 'Sesión activa';
  notice('login-message', '');
  $('password').value = '';
  try {
    const data = await graphql(ME, {}, session.token);
    session = {
      ...session,
      companyId: data.me.companyId,
      companyName: data.me.companyName,
      permissions: data.me.permissions || [],
      role: data.me.role,
      isAdmin: data.me.isAdmin,
      user: data.me.user,
    };
    saveSession(session);
    $('company-label').textContent = data.me.companyName;
    $('company').textContent = `${data.me.companyName} · Empresa ${data.me.companyId}`;
    $('nav-users').hidden = !can('company.users.read');
    $('nav-accounts').hidden = !can('accounts.read');
    $('nav-concepts').hidden = !can('concepts.read');
    $('nav-roles').hidden = !can('roles.read');
    const adminPanels = allowedAdminPanels();
    $('nav-admin').hidden = adminPanels.length === 0;
    if (adminPanels.length && !adminPanels.includes(currentAdmin)) {
      currentAdmin = adminPanels[0];
    }
    if (currentView === 'admin' && adminPanels.length === 0) {
      currentView = 'financial';
    }
    $('users-new').hidden = !can('company.users.write');
    $('accounts-new').hidden = !can('accounts.write');
    $('concepts-new').hidden = !can('concepts.write');
    $('assignment-new').hidden = !can('concepts.write');
    setView(currentView);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('login-message', error.message);
  }
}

function validateBalance(balance, from, to) {
  if (!balance || balance.currency !== 'MXN' || balance.fromDate !== from || balance.toDate !== to || !Array.isArray(balance.accounts)) {
    throw new Error('La respuesta no corresponde al período o a la moneda solicitada. Vuelve a consultar.');
  }
  fields.forEach(field => money(balance[field]));
  for (const account of balance.accounts) fields.forEach(field => money(account[field]));
}

function render(balance) {
  $('company').textContent = `${balance.companyName} · Empresa ${balance.companyId}`;
  $('applied-period').textContent = `${dateLabel(balance.fromDate)} al ${dateLabel(balance.toDate)}`;
  fields.forEach(field => {
    const node = $(field);
    node.textContent = money(balance[field]);
    node.classList.toggle('negative', field !== 'profit' && negative(balance[field]));
    node.classList.toggle('profit-loss', field === 'profit' && negative(balance[field]));
  });
  $('general-risk').textContent = `General en rojo: ${balance.isInRed ? 'Sí' : 'No'}`;
  $('general-risk').classList.toggle('risk-alert', balance.isInRed);
  $('risk-dot').classList.toggle('red', balance.isInRed);
  $('accounts-risk').textContent = `Cuentas en rojo: ${balance.accountsInRed}`;
  $('accounts-risk').classList.toggle('risk-alert', balance.accountsInRed > 0);
  $('account-count').textContent = `${balance.accounts.length} ${balance.accounts.length === 1 ? 'cuenta' : 'cuentas'}`;
  $('no-movements').hidden = balance.transactionCount !== 0 || balance.accounts.length === 0;
  $('empty-accounts').hidden = balance.accounts.length !== 0;
  $('table-wrapper').hidden = balance.accounts.length === 0;
  const rows = balance.accounts.map(account => {
    const row = document.createElement('tr');
    const cell = (text, className = '') => {
      const td = document.createElement('td');
      td.textContent = text;
      td.className = className;
      row.append(td);
      return td;
    };
    const name = cell(account.accountName);
    const id = document.createElement('small');
    id.textContent = `ID ${account.accountId}`;
    name.append(id);
    const badgeCell = (label, className) => {
      const td = cell('');
      td.append(badge(label, className));
    };
    badgeCell(account.isActive ? 'Activa' : 'Inactiva', account.isActive ? '' : 'inactive');
    fields.forEach(field => cell(money(account[field]), negative(account[field]) ? (field === 'profit' ? 'profit-loss' : 'negative') : ''));
    badgeCell(account.isInRed ? 'En rojo' : 'Sin saldo negativo', account.isInRed ? 'red' : '');
    return row;
  });
  $('account-rows').replaceChildren(...rows);
  $('results').hidden = false;
}

async function loadBalance() {
  if (!session || currentView !== 'financial') return;
  pending?.abort();
  const version = ++requestId;
  const from = $('from-date').value;
  const to = $('to-date').value;
  clearResults();
  if (!validPeriod(from, to)) {
    notice('status', 'Revisa las fechas: el inicio debe ser igual o anterior al final y ambas fechas deben ser válidas.');
    $('refresh').disabled = false;
    return;
  }
  pending = new AbortController();
  $('refresh').disabled = true;
  notice('status', 'Consultando el balance…', true);
  try {
    const result = await graphql(BALANCE, { from, to }, session.token, pending.signal);
    if (version !== requestId) return;
    validateBalance(result.generalBalance, from, to);
    render(result.generalBalance);
    notice('status', '');
  } catch (error) {
    if (error.name === 'AbortError' || version !== requestId) return;
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('status', error.message);
  } finally {
    if (version === requestId) $('refresh').disabled = false;
  }
}

function filteredUsers() {
  const term = $('users-search').value.trim().toLowerCase();
  const filter = $('users-filter').value;
  return usersCache.filter(item => {
    const haystack = `${item.user.name} ${item.user.email}`.toLowerCase();
    if (term && !haystack.includes(term)) return false;
    if (filter === 'active' && !item.isActive) return false;
    if (filter === 'inactive' && item.isActive) return false;
    return true;
  });
}

function renderUsers() {
  const active = usersCache.filter(item => item.isActive).length;
  const admins = usersCache.filter(item => item.isAdmin).length;
  const inactive = usersCache.filter(item => !item.isActive).length;
  $('users-active-count').textContent = String(active);
  $('users-admin-count').textContent = String(admins);
  $('users-inactive-count').textContent = String(inactive);
  const note = $('users-admin-note');
  if (admins > 1) {
    note.hidden = false;
    note.textContent = 'Inconsistencia: hay más de un administrador principal.';
  } else {
    note.hidden = true;
    note.textContent = '';
  }
  const rows = filteredUsers().map(item => {
    const row = document.createElement('tr');
    const nameTd = document.createElement('td');
    nameTd.textContent = item.user.name;
    row.append(nameTd);

    const emailTd = document.createElement('td');
    emailTd.textContent = item.user.email;
    row.append(emailTd);

    const roleTd = document.createElement('td');
    if (can('roles.write') && rolesCache.length) {
      const editor = document.createElement('div');
      editor.className = 'role-editor';
      const select = document.createElement('select');
      select.setAttribute('aria-label', `Rol de ${item.user.name}`);
      if (!item.role) {
        const emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = 'Sin rol asignado';
        emptyOpt.disabled = true;
        emptyOpt.selected = true;
        select.append(emptyOpt);
      }
      rolesCache.forEach(role => {
        const opt = document.createElement('option');
        opt.value = role.id;
        opt.textContent = role.name;
        if (item.role?.id === role.id || item.role?.code === role.code) opt.selected = true;
        select.append(opt);
      });
      const saveBtn = document.createElement('button');
      saveBtn.type = 'button';
      saveBtn.className = 'role-save';
      saveBtn.textContent = 'Guardar';
      saveBtn.addEventListener('click', () => assignUserRole(item, select, saveBtn));
      editor.append(select, saveBtn);
      roleTd.append(editor);
    } else {
      roleTd.textContent = item.role?.name || 'Sin rol asignado';
    }
    row.append(roleTd);

    const adminTd = document.createElement('td');
    adminTd.textContent = item.isAdmin ? 'Sí' : 'No';
    row.append(adminTd);

    const state = document.createElement('td');
    state.append(badge(item.isActive ? 'Activo' : 'Inactivo', item.isActive ? '' : 'inactive'));
    row.append(state);

    const actions = document.createElement('td');
    if (can('company.users.write') && item.isActive && !item.isAdmin) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'text-button danger';
      button.textContent = 'Desactivar';
      button.addEventListener('click', () => deactivateUser(item.id, button));
      actions.append(button);
    } else {
      actions.textContent = '—';
    }
    row.append(actions);
    return row;
  });
  $('users-rows').replaceChildren(...rows);
  $('users-empty').hidden = rows.length !== 0;
}

async function loadUsers() {
  notice('admin-status', 'Cargando usuarios…', true);
  try {
    const requests = [graphql(COMPANY_USERS, {}, session.token)];
    if (can('roles.write') && can('roles.read')) {
      requests.push(graphql(ACTIVE_ROLES, {}, session.token));
    }
    const [usersData, rolesData] = await Promise.all(requests);
    usersCache = usersData.companyUsers;
    if (rolesData) rolesCache = orderedRoles(rolesData.roles);
    renderUsers();
    notice('admin-status', '');
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  }
}

async function assignUserRole(item, select, button) {
  const previousRoleId = item.role?.id || '';
  const selectedRoleId = select.value;
  if (!selectedRoleId) {
    notice('admin-status', 'Selecciona un rol activo para asignar.');
    return;
  }
  select.disabled = true;
  button.disabled = true;
  notice('admin-status', `Guardando puesto de ${item.user.name}…`, true);
  try {
    const data = await graphql(
      ASSIGN_ROLE,
      { input: { companyUserId: item.id, roleId: selectedRoleId } },
      session.token,
    );
    const assigned = data.assignRole.role;
    await loadUsers();
    notice(
      'admin-status',
      `${item.user.name} ahora tiene el puesto ${assigned.name}. Administrador principal sigue en ${item.isAdmin ? 'Sí' : 'No'}.`,
      true,
    );
  } catch (error) {
    select.value = previousRoleId;
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    select.disabled = false;
    button.disabled = false;
  }
}

async function deactivateUser(id, button) {
  button.disabled = true;
  notice('admin-status', 'Desactivando membresía…', true);
  try {
    await graphql(
      `mutation($id: ID!) { deactivateCompanyUser(id: $id) { id isActive } }`,
      { id },
      session.token,
    );
    await loadUsers();
    notice('admin-status', 'El usuario quedó inactivo. El historial se conserva.', true);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    button.disabled = false;
  }
}

function filteredAccounts() {
  const type = $('accounts-type-filter').value;
  const activeOnly = $('accounts-active-only').checked;
  return accountsCache.filter(item => {
    if (type !== 'all' && item.accountType !== type) return false;
    if (activeOnly && !item.isActive) return false;
    return true;
  });
}

function renderAccounts() {
  const rows = filteredAccounts().map(item => {
    const row = document.createElement('tr');
    [
      item.name,
      ACCOUNT_LABELS[item.accountType] || item.accountType,
      item.bankName || '—',
      maskReference(item),
    ].forEach(text => {
      const td = document.createElement('td');
      td.textContent = text;
      row.append(td);
    });
    const state = document.createElement('td');
    state.append(badge(item.isActive ? 'Activa' : 'Inactiva', item.isActive ? '' : 'inactive'));
    row.append(state);
    return row;
  });
  $('accounts-rows').replaceChildren(...rows);
  $('accounts-empty').hidden = rows.length !== 0;
}

async function loadAccounts() {
  notice('admin-status', 'Cargando cuentas…', true);
  try {
    const data = await graphql(ACCOUNTS, {}, session.token);
    accountsCache = data.accounts;
    renderAccounts();
    fillAssignmentAccounts();
    notice('admin-status', '');
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  }
}

function filteredConcepts() {
  const type = $('concepts-type-filter').value;
  const activeOnly = $('concepts-active-only').checked;
  return conceptsCache.filter(item => {
    if (type !== 'all' && item.conceptType !== type) return false;
    if (activeOnly && !item.isActive) return false;
    return true;
  });
}

function renderConcepts() {
  const rows = filteredConcepts().map(item => {
    const row = document.createElement('tr');
    [item.name, CONCEPT_LABELS[item.conceptType] || item.conceptType].forEach(text => {
      const td = document.createElement('td');
      td.textContent = text;
      row.append(td);
    });
    const state = document.createElement('td');
    state.append(badge(item.isActive ? 'Activo' : 'Inactivo', item.isActive ? '' : 'inactive'));
    row.append(state);
    return row;
  });
  $('concepts-rows').replaceChildren(...rows);
  $('concepts-empty').hidden = rows.length !== 0;
  fillAssignmentConcepts();
}

function fillAssignmentAccounts() {
  const select = $('assignment-account');
  const current = select.value;
  const options = accountsCache.filter(item => item.isActive).map(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.name;
    return option;
  });
  if (!options.length) {
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = 'No hay cuentas activas';
    select.replaceChildren(empty);
    select.disabled = true;
    assignmentsCache = [];
    renderAssignments();
    return;
  }
  select.disabled = false;
  select.replaceChildren(...options);
  if (current && [...select.options].some(option => option.value === current)) select.value = current;
  loadAssignments();
}

function fillAssignmentConcepts() {
  const select = $('assignment-concept');
  const assigned = new Set(assignmentsCache.filter(item => item.isActive).map(item => item.concept.id));
  const options = conceptsCache
    .filter(item => item.isActive && !assigned.has(item.id))
    .map(item => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = `${item.name} (${CONCEPT_LABELS[item.conceptType] || item.conceptType})`;
      return option;
    });
  if (!options.length) {
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = 'No hay conceptos disponibles para asignar';
    select.replaceChildren(empty);
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.replaceChildren(...options);
}

function renderAssignments() {
  const active = assignmentsCache.filter(item => item.isActive);
  const rows = active.map(item => {
    const row = document.createElement('tr');
    [item.concept.name, CONCEPT_LABELS[item.concept.conceptType] || item.concept.conceptType].forEach(text => {
      const td = document.createElement('td');
      td.textContent = text;
      row.append(td);
    });
    const state = document.createElement('td');
    state.append(badge('Activo'));
    row.append(state);
    const actions = document.createElement('td');
    if (can('concepts.write')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'text-button danger';
      button.textContent = 'Quitar';
      button.addEventListener('click', () => removeAssignment(item.concept.id, button));
      actions.append(button);
    } else {
      actions.textContent = '—';
    }
    row.append(actions);
    return row;
  });
  $('assignment-rows').replaceChildren(...rows);
  const accountId = $('assignment-account').value;
  if (!accountId) {
    $('assignment-empty').textContent = 'Selecciona una cuenta para ver sus conceptos permitidos.';
    $('assignment-empty').hidden = false;
  } else if (!rows.length) {
    $('assignment-empty').textContent = 'Esta cuenta todavía no tiene conceptos asignados.';
    $('assignment-empty').hidden = false;
  } else {
    $('assignment-empty').hidden = true;
  }
  fillAssignmentConcepts();
}

async function loadConcepts() {
  notice('admin-status', 'Cargando conceptos…', true);
  try {
    const [accounts, concepts] = await Promise.all([
      graphql(ACCOUNTS, {}, session.token),
      graphql(CONCEPTS, {}, session.token),
    ]);
    accountsCache = accounts.accounts;
    conceptsCache = concepts.concepts;
    renderConcepts();
    fillAssignmentAccounts();
    notice('admin-status', '');
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  }
}

async function loadAssignments() {
  const accountId = $('assignment-account').value;
  if (!accountId) {
    assignmentsCache = [];
    renderAssignments();
    return;
  }
  try {
    const data = await graphql(ACCOUNT_CONCEPTS, { accountId }, session.token);
    assignmentsCache = data.accountConcepts;
    renderAssignments();
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  }
}

async function removeAssignment(conceptId, button) {
  const accountId = $('assignment-account').value;
  button.disabled = true;
  notice('admin-status', 'Quitando concepto de la cuenta…', true);
  try {
    await graphql(
      `mutation($accountId: ID!, $conceptId: ID!) { removeConceptFromAccount(accountId: $accountId, conceptId: $conceptId) }`,
      { accountId, conceptId },
      session.token,
    );
    await loadAssignments();
    notice('admin-status', 'La relación quedó inactiva. El concepto permanece en el catálogo.', true);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    button.disabled = false;
  }
}

function columnHasChanges(roleId) {
  const saved = matrixSaved.get(roleId) || new Set();
  const draft = matrixDraft.get(roleId) || new Set();
  if (saved.size !== draft.size) return true;
  for (const id of saved) if (!draft.has(id)) return true;
  return false;
}

function renderMatrix() {
  const groups = groupedPermissions(permissionsCache);
  const hasCatalog = rolesCache.length > 0 && groups.length > 0;
  $('roles-empty').hidden = hasCatalog;
  $('matrix-wrapper').hidden = !hasCatalog;
  $('roles-readonly-note').hidden = !hasCatalog || can('roles.write');
  if (!hasCatalog) {
    $('matrix-preview').hidden = true;
    return;
  }

  const headRow = document.createElement('tr');
  const firstTh = document.createElement('th');
  firstTh.scope = 'col';
  firstTh.textContent = 'Permiso';
  headRow.append(firstTh);
  rolesCache.forEach(role => {
    const th = document.createElement('th');
    th.scope = 'col';
    if (isReadOnlyRole(role)) th.className = 'col-readonly';
    th.textContent = role.name;
    const code = document.createElement('small');
    code.textContent = isReadOnlyRole(role) ? `${role.code} · solo lectura` : role.code;
    th.append(code);
    headRow.append(th);
  });
  $('matrix-head').replaceChildren(headRow);

  const bodyRows = [];
  const editable = can('roles.write');
  groups.forEach(group => {
    const groupTr = document.createElement('tr');
    groupTr.className = 'group-row';
    const groupTd = document.createElement('td');
    groupTd.colSpan = rolesCache.length + 1;
    groupTd.textContent = group.label;
    groupTr.append(groupTd);
    bodyRows.push(groupTr);

    group.permissions.forEach(permission => {
      const tr = document.createElement('tr');
      const labelTd = document.createElement('td');
      labelTd.textContent = permission.name;
      const codeEl = document.createElement('small');
      codeEl.textContent = permission.code;
      labelTd.append(codeEl);
      tr.append(labelTd);

      rolesCache.forEach(role => {
        const td = document.createElement('td');
        const saved = matrixSaved.get(role.id)?.has(permission.id) || false;
        const draft = matrixDraft.get(role.id)?.has(permission.id) || false;
        if (isReadOnlyRole(role)) {
          td.className = 'col-readonly';
          td.textContent = saved ? 'sí' : 'no';
        } else {
          if (draft !== saved) {
            td.className = draft ? 'cell-pending-add' : 'cell-pending-remove';
          }
          const label = document.createElement('label');
          label.className = `matrix-check${editable ? '' : ' disabled'}`;
          const input = document.createElement('input');
          input.type = 'checkbox';
          input.checked = draft;
          input.disabled = !editable;
          input.setAttribute('aria-label', `${permission.name} para ${role.name}`);
          const text = document.createElement('span');
          text.textContent = draft ? 'sí' : 'no';
          if (editable) {
            input.addEventListener('change', () => {
              const set = matrixDraft.get(role.id) || new Set();
              if (input.checked) set.add(permission.id);
              else set.delete(permission.id);
              matrixDraft.set(role.id, set);
              renderMatrix();
              if (activePreview?.role.id === role.id) previewColumn(role);
            });
          }
          label.append(input, text);
          td.append(label);
        }
        tr.append(td);
      });
      bodyRows.push(tr);
    });
  });
  $('matrix-body').replaceChildren(...bodyRows);

  if (editable) {
    const footRow = document.createElement('tr');
    const infoTd = document.createElement('td');
    infoTd.className = 'muted small';
    infoTd.textContent = 'Previsualiza y guarda por columna';
    footRow.append(infoTd);
    rolesCache.forEach(role => {
      const td = document.createElement('td');
      if (isReadOnlyRole(role)) {
        td.className = 'col-readonly muted small';
        td.textContent = 'Solo lectura';
      } else {
        const btn = document.createElement('button');
        btn.type = 'button';
        const dirty = columnHasChanges(role.id);
        btn.className = `matrix-col-btn${dirty ? ' dirty' : ''}`;
        btn.textContent = dirty ? 'Vista previa *' : 'Vista previa';
        btn.addEventListener('click', () => previewColumn(role));
        td.append(btn);
      }
      footRow.append(td);
    });
    $('matrix-foot').replaceChildren(footRow);
  } else {
    $('matrix-foot').replaceChildren();
    $('matrix-preview').hidden = true;
    activePreview = null;
  }
}

async function loadRolesMatrix() {
  activePreview = null;
  $('matrix-preview').hidden = true;
  notice('admin-status', 'Cargando matriz de roles y permisos…', true);
  try {
    const catalog = await graphql(MATRIX_CATALOG, {}, session.token);
    rolesCache = orderedRoles(catalog.roles);
    permissionsCache = catalog.permissions || [];
    if (!rolesCache.length || !permissionsCache.length) {
      matrixSaved = new Map();
      matrixDraft = new Map();
      renderMatrix();
      notice('admin-status', '');
      return;
    }
    const columns = await Promise.all(
      rolesCache.map(role => graphql(ROLE_PERMISSIONS, { roleId: role.id }, session.token)),
    );
    matrixSaved = new Map();
    matrixDraft = new Map();
    rolesCache.forEach((role, index) => {
      const activeIds = new Set(
        (columns[index].rolePermissions || [])
          .filter(item => item.isActive && item.permission?.id)
          .map(item => item.permission.id),
      );
      matrixSaved.set(role.id, activeIds);
      matrixDraft.set(role.id, new Set(activeIds));
    });
    renderMatrix();
    notice('admin-status', '');
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  }
}

async function previewColumn(role) {
  if (isReadOnlyRole(role) || !can('roles.write')) return;
  const permissionIds = [...(matrixDraft.get(role.id) || [])];
  notice('admin-status', `Calculando vista previa para ${role.name}…`, true);
  try {
    const data = await graphql(
      PREVIEW_ROLE_PERMISSIONS,
      { input: { roleId: role.id, permissionIds } },
      session.token,
    );
    const plan = data.previewRolePermissions;
    activePreview = { role, permissionIds, plan };
    $('preview-title').textContent = `Vista previa · ${role.code}`;
    $('preview-activate').textContent = plan.toActivate.map(p => p.code).join(', ') || 'ninguno';
    $('preview-deactivate').textContent = plan.toDeactivate.map(p => p.code).join(', ') || 'ninguno';
    $('preview-unchanged').textContent = String(plan.unchanged.length);
    $('preview-final').textContent = String(plan.finalCount);
    $('preview-count').textContent = `Total final: ${plan.finalCount}`;
    $('matrix-preview').hidden = false;
    notice('admin-status', '');
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  }
}

async function savePreviewColumn() {
  if (!activePreview || isReadOnlyRole(activePreview.role) || !can('roles.write')) return;
  const { role, permissionIds } = activePreview;
  $('preview-save').disabled = true;
  notice('admin-status', `Guardando columna ${role.name}…`, true);
  try {
    const data = await graphql(
      SET_ROLE_PERMISSIONS,
      { input: { roleId: role.id, permissionIds } },
      session.token,
    );
    const result = data.setRolePermissions;
    const reloaded = await graphql(ROLE_PERMISSIONS, { roleId: role.id }, session.token);
    const activeIds = new Set(
      (reloaded.rolePermissions || [])
        .filter(item => item.isActive && item.permission?.id)
        .map(item => item.permission.id),
    );
    matrixSaved.set(role.id, activeIds);
    matrixDraft.set(role.id, new Set(activeIds));
    renderMatrix();

    if (result.changed) {
      const act = result.activated.map(p => p.code).join(', ') || 'ninguno';
      const deact = result.deactivated.map(p => p.code).join(', ') || 'ninguno';
      notice(
        'admin-status',
        `Columna ${role.name} (${role.code}) guardada (changed: true). Activados: ${act}. Desactivados: ${deact}. Total final: ${result.finalCount}.`,
        true,
      );
    } else {
      notice(
        'admin-status',
        `Sin cambios (changed: false). La columna ${role.name} (${role.code}) ya tenía esos ${result.finalCount} permisos activos; no se duplicaron filas.`,
        true,
      );
    }
    $('preview-activate').textContent = 'ninguno';
    $('preview-deactivate').textContent = 'ninguno';
    $('preview-unchanged').textContent = String(result.finalCount);
    $('preview-final').textContent = String(result.finalCount);
    $('preview-count').textContent = `Total final: ${result.finalCount}`;
    activePreview = { role, permissionIds: [...activeIds], plan: null };
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    $('preview-save').disabled = false;
  }
}

function discardPreview() {
  if (activePreview) {
    const { role } = activePreview;
    matrixDraft.set(role.id, new Set(matrixSaved.get(role.id) || []));
    activePreview = null;
    $('matrix-preview').hidden = true;
    renderMatrix();
    notice('admin-status', `Cambios descartados en ${role.name}.`, true);
  }
}

$('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('login-button').disabled = true;
  notice('login-message', 'Validando tu sesión…', true);
  const input = { email: $('email').value.trim(), password: $('password').value };
  if ($('membership').value.trim()) input.companyUserId = $('membership').value.trim();
  try {
    const { login } = await graphql(LOGIN, { input });
    if (!login.token || login.tokenType.toLowerCase() !== 'bearer') {
      throw new Error('La respuesta de inicio de sesión no es válida.');
    }
    saveSession({ token: login.token, user: login.user });
    await showApp();
  } catch (error) {
    notice('login-message', error.message);
    if (/membresía/.test(error.message)) $('membership-options').open = true;
  } finally {
    $('login-button').disabled = false;
  }
});

$('period-form').addEventListener('submit', event => {
  event.preventDefault();
  loadBalance();
});
['from-date', 'to-date'].forEach(id => $(id).addEventListener('change', loadBalance));
$('demo-period').addEventListener('click', () => {
  $('from-date').value = '2026-10-26';
  $('to-date').value = '2026-10-30';
  loadBalance();
});
$('logout').addEventListener('click', () => logout());

$('nav-financial').addEventListener('click', () => setView('financial'));
$('nav-admin').addEventListener('click', () => setView('admin'));
document.querySelectorAll('.subnav-item').forEach(node => {
  node.addEventListener('click', () => setAdminPanel(node.dataset.admin));
});

$('users-search').addEventListener('input', renderUsers);
$('users-filter').addEventListener('change', renderUsers);
$('users-new').addEventListener('click', () => {
  $('users-form').hidden = false;
  $('user-name-input').focus();
});
$('users-cancel').addEventListener('click', () => {
  $('users-form').hidden = true;
  $('users-form').reset();
});
$('users-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('users-save').disabled = true;
  notice('admin-status', 'Registrando usuario…', true);
  try {
    await graphql(
      `mutation($input: CreateCompanyUserInput!) {
        createCompanyUser(input: $input) { id user { email } }
      }`,
      {
        input: {
          companyId: session.companyId,
          name: $('user-name-input').value.trim(),
          email: $('user-email-input').value.trim(),
          password: $('user-password-input').value,
        },
      },
      session.token,
    );
    $('users-form').reset();
    $('users-form').hidden = true;
    await loadUsers();
    notice('admin-status', 'Usuario creado correctamente.', true);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    $('users-save').disabled = false;
  }
});

$('accounts-type-filter').addEventListener('change', renderAccounts);
$('accounts-active-only').addEventListener('change', renderAccounts);
$('accounts-new').addEventListener('click', () => {
  $('accounts-form').hidden = false;
  $('account-name-input').focus();
});
$('accounts-cancel').addEventListener('click', () => {
  $('accounts-form').hidden = true;
  $('accounts-form').reset();
});
$('accounts-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('accounts-save').disabled = true;
  notice('admin-status', 'Registrando cuenta…', true);
  try {
    const bank = $('account-bank-input').value.trim();
    const clabe = $('account-clabe-input').value.trim();
    const shortDescription = $('account-desc-input').value.trim();
    await graphql(
      `mutation($input: CreateAccountInput!) {
        createAccount(input: $input) { id name }
      }`,
      {
        input: {
          companyId: session.companyId,
          accountType: $('account-type-input').value,
          name: $('account-name-input').value.trim(),
          bankName: bank || null,
          clabe: clabe || null,
          shortDescription: shortDescription || null,
        },
      },
      session.token,
    );
    $('accounts-form').reset();
    $('accounts-form').hidden = true;
    await loadAccounts();
    notice('admin-status', 'Cuenta creada correctamente.', true);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    $('accounts-save').disabled = false;
  }
});

$('concepts-type-filter').addEventListener('change', renderConcepts);
$('concepts-active-only').addEventListener('change', renderConcepts);
$('concepts-new').addEventListener('click', () => {
  $('concepts-form').hidden = false;
  $('concept-name-input').focus();
});
$('concepts-cancel').addEventListener('click', () => {
  $('concepts-form').hidden = true;
  $('concepts-form').reset();
});
$('concepts-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('concepts-save').disabled = true;
  notice('admin-status', 'Registrando concepto…', true);
  try {
    const shortDescription = $('concept-desc-input').value.trim();
    await graphql(
      `mutation($input: CreateConceptInput!) {
        createConcept(input: $input) { id name }
      }`,
      {
        input: {
          companyId: session.companyId,
          conceptType: $('concept-type-input').value,
          name: $('concept-name-input').value.trim(),
          shortDescription: shortDescription || null,
        },
      },
      session.token,
    );
    $('concepts-form').reset();
    $('concepts-form').hidden = true;
    await loadConcepts();
    notice('admin-status', 'Concepto creado correctamente.', true);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    $('concepts-save').disabled = false;
  }
});

$('assignment-account').addEventListener('change', loadAssignments);
$('assignment-new').addEventListener('click', () => {
  $('assignment-form').hidden = false;
});
$('assignment-cancel').addEventListener('click', () => {
  $('assignment-form').hidden = true;
});
$('assignment-form').addEventListener('submit', async event => {
  event.preventDefault();
  const accountId = $('assignment-account').value;
  const conceptId = $('assignment-concept').value;
  if (!accountId || !conceptId) {
    notice('admin-status', 'Selecciona una cuenta y un concepto para asignar.');
    return;
  }
  $('assignment-save').disabled = true;
  notice('admin-status', 'Asignando concepto…', true);
  try {
    await graphql(
      `mutation($input: AssignConceptToAccountInput!) {
        assignConceptToAccount(input: $input) { id }
      }`,
      { input: { accountId, conceptId } },
      session.token,
    );
    $('assignment-form').hidden = true;
    await loadAssignments();
    notice('admin-status', 'Concepto asignado a la cuenta.', true);
  } catch (error) {
    if (error.code === 'UNAUTHENTICATED') logout(error.message);
    else notice('admin-status', error.message);
  } finally {
    $('assignment-save').disabled = false;
  }
});

$('preview-save').addEventListener('click', savePreviewColumn);
$('preview-discard').addEventListener('click', discardPreview);

function defaultPeriod() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  $('from-date').value = `${year}-${month}-01`;
  $('to-date').value = `${year}-${month}-${String(now.getDate()).padStart(2, '0')}`;
}

defaultPeriod();
try {
  const stored = JSON.parse(sessionStorage.getItem(KEY));
  if (stored && typeof stored.token === 'string') session = stored;
} catch {
  saveSession(null);
}
if (session) showApp();
