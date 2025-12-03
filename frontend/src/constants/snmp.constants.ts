export enum AttackCategory {
  INTRUSIONS = 'Intrusions',
  DOS = 'DoS',
  ANOMALIES = 'Anomalies',
  ANTI_SCANNING = 'Anti-Scanning',
  BEHAVIORAL_DOS = 'Behavioral-DoS',
  SYN_FLOOD = 'SynFlood',
  ACCESS = 'Access',
  HTTP_FLOOD = 'HttpFlood',
  CRACKING_PROTECTION = 'Cracking-Protection',
  STATEFUL_ACL = 'Stateful-ACL',
  SESSION_TABLE_PROTECTION = 'Session-Table-Protection',
  BWM = 'BWM',
  DNS_PROTECTION = 'DNS-Protection',
  TRAFFIC_FILTERS = 'Traffic-Filters',
  HTTPS = 'Https',
  GEO_FEED = 'GeoFeed',
  ERT_FEED = 'ErtFeed',
  CONNECTION_PPS = 'ConnectionPPS',
  QUANTILE_DOS = 'Quantile-DoS',
  L7APP_SIG = 'L7AppSig',
  WEB_DDOS = 'Web-DDoS',
}

export enum AttackProtocol {
  IP = 'IP',
  TCP = 'TCP',
  UDP = 'UDP',
  ICMP = 'ICMP',
  NON_IP = 'Non-IP',
  SCTP = 'SCTP',
  ICMPV6 = 'ICMPv6',
}

export enum AttackStatus {
  DISCRETE = 'discrete',
  START = 'start',
  ONGOING = 'ongoing',
  TERM = 'term',
  OCCUR = 'occur',
  LIMITED = 'limited',
  SAMPLED = 'sampled',
  AGGREGATED = 'aggregated',
  AGGRESSIVE = 'aggressive',
}

export enum AttackRisk {
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
  INFO = 'info',
  NA = 'N/A',
}

export enum AttackAction {
  FORWARD = 'forward',
  CHALLENGE = 'challenge',
  DROP = 'drop',
  SOURCE_RESET = 'source-reset',
  DEST_RESET = 'dest-reset',
  SOURCE_DEST_RESET = 'source-dest-reset',
  APP_RESET = 'app-reset',
  QUARANTINE = 'quarantine',
  DROP_AND_QUARANTINE = 'drop-and-quarantine',
  HTTP_200_OK = 'http-200-ok',
  HTTP_200_OK_RESET_DEST = 'http-200-ok-reset-dest',
  HTTP_403_FORBIDDEN = 'http-403-forbidden',
  HTTP_403_FORBIDDEN_RESET_DEST = 'http-403-forbidden-reset-dest',
}

export enum AttackDirection {
  UNKNOWN = 'unknown',
  IN = 'in',
  OUT = 'out',
}

export const SNMP_FIELD_DEFAULTS = {
  attackCategory: AttackCategory.BEHAVIORAL_DOS,
  protocol: AttackProtocol.TCP,
  srcIp: '0.0.0.0',
  srcPort: '80',
  dstIp: '0.0.0.0',
  dstPort: '80',
  physicalPort: '1',
  status: AttackStatus.ONGOING,
  packetCount: '1000',
  packetBandwidth: '2000',
  samples: '0-0-0',
  risk: AttackRisk.MEDIUM,
  action: AttackAction.DROP,
  direction: AttackDirection.IN,
};

