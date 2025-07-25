export enum DynamicSamplingBiasType {
  BOOST_ENVIRONMENTS = 'boostEnvironments',
  BOOST_LATEST_RELEASES = 'boostLatestRelease',
  BOOST_LOW_VOLUME_TRANSACTIONS = 'boostLowVolumeTransactions',
  IGNORE_HEALTH_CHECKS = 'ignoreHealthChecks',
  MINIMUM_SAMPLE_RATE = 'minimumSampleRate',
}

export type DynamicSamplingBias = {
  active: boolean;
  id: DynamicSamplingBiasType;
};
