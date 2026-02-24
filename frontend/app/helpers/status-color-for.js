import { helper } from '@ember/component/helper';

const STATUS_COLORS = {
  pending: '#fd7e14',
  running: '#0d6efd',
  completed: '#198754',
  failed: '#dc3545',
};

export default helper(function statusColorFor([status]) {
  return STATUS_COLORS[status] ?? '#6c757d';
});
