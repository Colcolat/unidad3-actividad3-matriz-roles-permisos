import assert from 'node:assert/strict';
import { orderedRoles, groupedPermissions, isReadOnlyRole } from './matrix.mjs';

const roles = orderedRoles([
  { id: '4', code: 'CONSULTA', name: 'Consulta' },
  { id: '99', code: 'SIN_LECTURA_DEMO', name: 'Extra' },
  { id: '2', code: 'CONTADOR', name: 'Contador' },
  { id: '1', code: 'ADMINISTRADOR', name: 'Administrador' },
  { id: '3', code: 'CAPTURISTA', name: 'Capturista' },
]);

assert.deepEqual(roles.map(r => r.code), ['ADMINISTRADOR', 'CONTADOR', 'CAPTURISTA', 'CONSULTA']);
assert.equal(isReadOnlyRole(roles[0]), true);
assert.equal(isReadOnlyRole(roles[1]), false);

const groups = groupedPermissions([
  { id: '10', code: 'roles.write', name: 'Administrar roles y permisos' },
  { id: '9', code: 'roles.read', name: 'Consultar roles y permisos' },
  { id: '2', code: 'company.users.write', name: 'Administrar membresías' },
  { id: '1', code: 'company.users.read', name: 'Consultar membresías' },
  { id: '4', code: 'accounts.write', name: 'Crear cuentas' },
  { id: '3', code: 'accounts.read', name: 'Consultar cuentas' },
  { id: '6', code: 'concepts.write', name: 'Administrar conceptos' },
  { id: '5', code: 'concepts.read', name: 'Consultar conceptos' },
  { id: '8', code: 'transactions.write', name: 'Registrar movimientos' },
  { id: '7', code: 'transactions.read', name: 'Consultar movimientos' },
]);

assert.deepEqual(groups.map(g => g.label), ['Usuarios', 'Cuentas', 'Conceptos', 'Movimientos', 'Roles']);
assert.deepEqual(groups[0].permissions.map(p => p.code), ['company.users.read', 'company.users.write']);
assert.deepEqual(groups[1].permissions.map(p => p.code), ['accounts.read', 'accounts.write']);
assert.deepEqual(groups[4].permissions.map(p => p.code), ['roles.read', 'roles.write']);

const withoutOne = groupedPermissions([
  { id: '1', code: 'company.users.read', name: 'Consultar membresías' },
]);
assert.equal(withoutOne.length, 1);
assert.deepEqual(withoutOne[0].permissions.map(p => p.code), ['company.users.read']);

console.log('matrix.test.mjs OK');
