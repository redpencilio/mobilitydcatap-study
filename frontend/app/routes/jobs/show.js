import Route from '@ember/routing/route';
import { inject as service } from '@ember/service';

export default class JobsShowRoute extends Route {
  @service store;

  model({ job_id }) {
    return this.store.findRecord('job', job_id);
  }

  setupController(controller, model) {
    super.setupController(controller, model);
    if (!model.isFinished) {
      controller.pollJob.perform();
    }
  }

  resetController(controller) {
    controller.pollJob.cancelAll();
  }
}
