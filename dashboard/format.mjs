/** Formatea texto decimal sin convertirlo a Number ni sumar importes. */
export function money(value) {
  if (typeof value !== 'string' || !/^-?\d+(\.\d{1,2})?$/.test(value)) throw new Error('El servidor devolvió un importe inválido.');
  const negative = value.startsWith('-');
  const [whole, fraction = ''] = value.replace(/^-/, '').split('.');
  const integer = whole.replace(/^0+(?=\d)/, '');
  const decimals = fraction.padEnd(2, '0');
  const sign = negative && !/^0+$/.test(integer + decimals) ? '-' : '';
  return `${sign}$${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${decimals}`;
}
export function validPeriod(from, to) {
  const validDate = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '0001-01-01' || value > '9999-12-30') return false;
    const parsed = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  };
  return validDate(from) && validDate(to) && from <= to;
}
export const negative = value => /^-/.test(value) && !/^-0(?:\.0+)?$/.test(value);
export const dateLabel = value => value.split('-').reverse().join('/');
