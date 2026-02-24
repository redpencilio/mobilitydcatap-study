import Model, { attr } from '@ember-data/model';

export default class JobModel extends Model {
  @attr('string') sourceUrl;
  @attr('string') status;
  @attr('string') endpointType;
  @attr('string') reportUrl;
  @attr('string') errorMessage;
  @attr('string') graphUri;
  @attr('date') createdAt;
  @attr('date') startedAt;
  @attr('date') finishedAt;

  get isPending() {
    return this.status === 'pending';
  }

  get isRunning() {
    return this.status === 'running';
  }

  get isCompleted() {
    return this.status === 'completed';
  }

  get isFailed() {
    return this.status === 'failed';
  }

  get isFinished() {
    return this.isCompleted || this.isFailed;
  }
}
