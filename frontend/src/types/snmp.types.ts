import { AttackCategory, AttackProtocol, AttackStatus, AttackRisk, AttackAction, AttackDirection } from '../constants/snmp.constants';

export interface SNMPTrap {
  attackName: string;
  policy: string;
  attackId?: string;
  radwareId?: string;
  attackCategory?: AttackCategory;
  protocol?: AttackProtocol;
  srcIp?: string;
  srcPort?: string;
  dstIp?: string;
  dstPort?: string;
  physicalPort?: string;
  status?: AttackStatus;
  packetCount?: string;
  packetBandwidth?: string;
  samples?: string;
  risk?: AttackRisk;
  action?: AttackAction;
  direction?: AttackDirection;
  pause?: number; // Optional pause in seconds (max 60)
  randomFields?: string[]; // Fields that should use random values on send
}

export interface SNMPPayload {
  traps: SNMPTrap[];
}

export interface SNMPResponse {
  success: boolean;
  message: string;
}

export interface SNMPFormErrors {
  attackName?: string;
  policy?: string;
  srcIp?: string;
  srcPort?: string;
  dstIp?: string;
  dstPort?: string;
  physicalPort?: string;
  packetCount?: string;
  packetBandwidth?: string;
  samples?: string;
}
