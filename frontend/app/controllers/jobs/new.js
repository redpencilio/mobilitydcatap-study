import Controller from '@ember/controller';
import { action } from '@ember/object';
import { inject as service } from '@ember/service';
import { tracked } from '@glimmer/tracking';
import { task } from 'ember-concurrency';

export default class JobsNewController extends Controller {
  @service store;
  @service router;

  @tracked endpointUrl = '';
  @tracked validationError = '';

  get recentJobs() {
    return this.model.recentJobs;
  }

  @action
  updateUrl(event) {
    this.endpointUrl = event.target.value;
    this.validationError = '';
  }

  submitJob = task({ drop: true }, async () => {
    const url = this.endpointUrl.trim();

    if (!url) {
      this.validationError = 'Please enter a DCAT endpoint URL.';
      return;
    }

    try {
      new URL(url);
    } catch {
      this.validationError = 'Please enter a valid URL (e.g. https://example.com/catalog.ttl)';
      return;
    }

    // Generate a unique named graph URI for this job
    const graphUri = `http://mu.semte.ch/graphs/validation/${crypto.randomUUID()}`;

    const job = this.store.createRecord('job', {
      sourceUrl: url,
      status: 'pending',
      graphUri,
      createdAt: new Date(),
    });

    await job.save();
    this.endpointUrl = '';
    this.router.transitionTo('jobs.show', job.id);
  });
}
