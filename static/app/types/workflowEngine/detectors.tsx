import type {
  DataCondition,
  DataConditionGroup,
} from 'sentry/types/workflowEngine/dataConditions';
import type {
  AlertRuleSensitivity,
  AlertRuleThresholdType,
  Dataset,
  EventTypes,
} from 'sentry/views/alerts/rules/metric/types';

/**
 * See SnubaQuerySerializer
 */
interface SnubaQuery {
  aggregate: string;
  dataset: Dataset;
  eventTypes: EventTypes[];
  id: string;
  query: string;
  /**
   * Time window in seconds
   */
  timeWindow: number;
  environment?: string;
}

/**
 * See DataSourceSerializer
 */
interface BaseDataSource {
  id: string;
  organizationId: string;
  sourceId: string;
  type: 'snuba_query_subscription' | 'uptime_subscription' | 'cron_subscription';
}

export interface SnubaQueryDataSource extends BaseDataSource {
  /**
   * See QuerySubscriptionSerializer
   */
  queryObj: {
    id: string;
    snubaQuery: SnubaQuery;
    status: number;
    subscription: string;
  } | null;
  type: 'snuba_query_subscription';
}

export interface UptimeSubscriptionDataSource extends BaseDataSource {
  /**
   * See UptimeSubscriptionSerializer
   */
  queryObj: {
    body: string | null;
    headers: Array<[string, string]>;
    intervalSeconds: number;
    method: string;
    timeoutMs: number;
    traceSampling: boolean;
    url: string;
  };
  type: 'uptime_subscription';
}

export interface CronSubscriptionDataSource extends BaseDataSource {
  /* TODO: Make this match the actual properties when implemented in backend */
  queryObj: {
    checkinMargin: number | null;
    failureIssueThreshold: number | null;
    maxRuntime: number | null;
    recoveryThreshold: number | null;
    schedule: string;
    scheduleType: 'crontab' | 'interval';
    timezone: string;
  };
  // TODO: Change this to the actual type when implemented in backend
  type: 'cron_subscription';
}

export type DetectorType =
  | 'error'
  | 'metric_issue'
  | 'uptime_subscription'
  | 'uptime_domain_failure';

interface BaseMetricDetectorConfig {
  thresholdPeriod: number;
}

/**
 * Configuration for static/threshold-based detection
 */
interface MetricDetectorConfigStatic extends BaseMetricDetectorConfig {
  detectionType: 'static';
}

/**
 * Configuration for percentage-based change detection
 */
interface MetricDetectorConfigPercent extends BaseMetricDetectorConfig {
  comparisonDelta: number;
  detectionType: 'percent';
}

/**
 * Configuration for dynamic/anomaly detection
 */
interface MetricDetectorConfigDynamic extends BaseMetricDetectorConfig {
  detectionType: 'dynamic';
  seasonality?: 'auto' | 'daily' | 'weekly' | 'monthly';
  sensitivity?: AlertRuleSensitivity;
  thresholdType?: AlertRuleThresholdType;
}

export type MetricDetectorConfig =
  | MetricDetectorConfigStatic
  | MetricDetectorConfigPercent
  | MetricDetectorConfigDynamic;

interface UptimeDetectorConfig {
  environment: string;
}

interface CronDetectorConfig {
  environment: string;
}

type BaseDetector = Readonly<{
  createdBy: string | null;
  dateCreated: string;
  dateUpdated: string;
  enabled: boolean;
  id: string;
  lastTriggered: string;
  name: string;
  owner: string | null;
  projectId: string;
  type: DetectorType;
  workflowIds: string[];
}>;

export interface MetricDetector extends BaseDetector {
  readonly alertRuleId: number | null;
  readonly conditionGroup: DataConditionGroup | null;
  readonly config: MetricDetectorConfig;
  readonly dataSources: [SnubaQueryDataSource];
  readonly type: 'metric_issue';
}

export interface UptimeDetector extends BaseDetector {
  readonly config: UptimeDetectorConfig;
  readonly dataSources: [UptimeSubscriptionDataSource];
  readonly type: 'uptime_domain_failure';
}

export interface CronDetector extends BaseDetector {
  readonly config: CronDetectorConfig;
  readonly dataSources: [CronSubscriptionDataSource];
  readonly type: 'uptime_subscription';
}

export interface ErrorDetector extends BaseDetector {
  // TODO: Add error detector type fields
  readonly type: 'error';
}

export type Detector = MetricDetector | UptimeDetector | CronDetector | ErrorDetector;

interface UpdateConditionGroupPayload {
  conditions: Array<Omit<DataCondition, 'id'>>;
  logicType: DataConditionGroup['logicType'];
}

interface UpdateSnubaDataSourcePayload {
  aggregate: string;
  dataset: string;
  environment: string | null;
  eventTypes: string[];
  query: string;
  queryType: number;
  timeWindow: number;
}

interface UpdateUptimeDataSourcePayload {
  intervalSeconds: number;
  method: string;
  timeoutMs: number;
  traceSampling: boolean;
  url: string;
}

interface UpdateCronDataSourcePayload {
  checkinMargin: number | null;
  failureIssueThreshold: number | null;
  maxRuntime: number | null;
  recoveryThreshold: number | null;
  schedule: string | [number, string]; // Crontab or interval
  scheduleType: 'crontab' | 'interval';
  timezone: string;
}

export interface BaseDetectorUpdatePayload {
  name: string;
  owner: Detector['owner'];
  projectId: Detector['projectId'];
  type: Detector['type'];
  workflowIds: string[];
  enabled?: boolean;
}

export interface UptimeDetectorUpdatePayload extends BaseDetectorUpdatePayload {
  dataSource: UpdateUptimeDataSourcePayload;
  type: 'uptime_domain_failure';
}

export interface MetricDetectorUpdatePayload extends BaseDetectorUpdatePayload {
  conditionGroup: UpdateConditionGroupPayload;
  config: MetricDetectorConfig;
  dataSource: UpdateSnubaDataSourcePayload;
  type: 'metric_issue';
}

export interface CronDetectorUpdatePayload extends BaseDetectorUpdatePayload {
  config: CronDetectorConfig;
  dataSource: UpdateCronDataSourcePayload;
  type: 'uptime_subscription';
}
