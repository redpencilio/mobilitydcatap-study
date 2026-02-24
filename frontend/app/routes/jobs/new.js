import Route from '@ember/routing/route';
import { inject as service } from '@ember/service';

export default class JobsNewRoute extends Route {
  @service store;

  async model() {
    const recentJobs = await this.store.query('job', {
      sort: '-created-at',
      'page[size]': 10,
    });
    return { recentJobs };
  }
}
