export const ROLE_ORDER = ['ADMINISTRADOR', 'CONTADOR', 'CAPTURISTA', 'CONSULTA'];

export const PERMISSION_GROUPS = [
  {
    key: 'users',
    label: 'Usuarios',
    codes: ['company.users.read', 'company.users.write'],
  },
  {
    key: 'accounts',
    label: 'Cuentas',
    codes: ['accounts.read', 'accounts.write'],
  },
  {
    key: 'concepts',
    label: 'Conceptos',
    codes: ['concepts.read', 'concepts.write'],
  },
  {
    key: 'transactions',
    label: 'Movimientos',
    codes: ['transactions.read', 'transactions.write'],
  },
  {
    key: 'roles',
    label: 'Roles',
    codes: ['roles.read', 'roles.write'],
  },
];

export function orderedRoles(roles) {
  const byCode = new Map((roles || []).map(role => [role.code, role]));
  return ROLE_ORDER.map(code => byCode.get(code)).filter(Boolean);
}

export function groupedPermissions(permissions) {
  const byCode = new Map((permissions || []).map(permission => [permission.code, permission]));
  return PERMISSION_GROUPS.map(group => ({
    key: group.key,
    label: group.label,
    permissions: group.codes.map(code => byCode.get(code)).filter(Boolean),
  })).filter(group => group.permissions.length > 0);
}

export function isReadOnlyRole(role) {
  return role?.code === 'ADMINISTRADOR';
}
