export default [
  {
    match: {
      predicate: {
        type: "uri",
        value: "http://mu.semte.ch/vocabularies/ext/status"
      },
      object: {
        type: "literal",
        value: "pending"
      }
    },
    callback: {
      url: "http://job-runner/delta",
      method: "POST"
    },
    options: {
      resourceFormat: "v0.0.1",
      gracePeriod: 1000,
      ignoreFromSelf: true
    }
  }
];
