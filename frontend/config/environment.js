'use strict';

module.exports = function (/* environment, appConfig */) {
  return {
    modulePrefix: 'frontend',
    podModulePrefix: 'frontend/pods',
    environment: process.env.EMBER_ENV || 'development',
    rootURL: '/',
    locationType: 'history',

    EmberENV: {
      EXTEND_PROTOTYPES: false,
      FEATURES: {},
    },

    APP: {},
  };
};
