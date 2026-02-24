import Controller from '@ember/controller';
import { inject as service } from '@ember/service';
import { task, timeout } from 'ember-concurrency';

const POLL_INTERVAL_MS = 3000;

export default class JobsShowController extends Controller {
  @service store;

  pollJob = task(async () => {
    while (!this.model.isFinished) {
      await timeout(POLL_INTERVAL_MS);
      await this.model.reload();
    }
  });

  get statusLabel() {
    const labels = {
      pending: 'Queued',
      running: 'Analyzing...',
      completed: 'Complete',
      failed: 'Failed',
    };
    return labels[this.model.status] ?? this.model.status;
  }

  get statusColor() {
    const colors = {
      pending: '#fd7e14',
      running: '#0d6efd',
      completed: '#198754',
      failed: '#dc3545',
    };
    return colors[this.model.status] ?? '#6c757d';
  }
}
