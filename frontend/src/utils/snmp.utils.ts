import { SNMPTrap } from '../types/snmp.types';
import {
  AttackCategory,
  AttackProtocol,
  AttackStatus,
  AttackRisk,
  AttackAction,
  AttackDirection,
} from '../constants/snmp.constants';

export const generateRadwareId = (): string => {
  return String(Math.floor(Math.random() * 999999) + 1);
};

export const generateAttackId = (): string => {
  const part1 = Math.floor(Math.random() * 900) + 100; // 100-999
  const currentEpoch = Math.floor(Date.now() / 1000); // Current epoch timestamp in seconds
  const part2 = Math.floor(Math.random() * (currentEpoch + 1)); // 0 to current epoch
  return `${part1}-${String(part2).padStart(10, '0')}`;
};

export const validateIPAddress = (ip: string): boolean => {
  if (!ip || ip.trim() === '') return false;

  // IPv4 validation with proper range checking
  const ipv4Pattern = /^(\d{1,3}\.){3}\d{1,3}$/;
  if (ipv4Pattern.test(ip)) {
    const parts = ip.split('.');
    return parts.every(part => {
      const num = parseInt(part, 10);
      return num >= 0 && num <= 255;
    });
  }

  // IPv6 validation - strict pattern that requires proper structure
  // Supports: full form, compressed (::), and IPv4-mapped (::ffff:192.0.2.1)
  // Does NOT accept trailing colons or incomplete addresses
  const ipv6Pattern = /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$/;

  return ipv6Pattern.test(ip);
};

export const validatePort = (port: string): boolean => {
  const portNum = parseInt(port, 10);
  return !isNaN(portNum) && portNum >= 0 && portNum <= 65535;
};

export const validatePositiveInteger = (value: string): boolean => {
  const num = parseInt(value, 10);
  return !isNaN(num) && num >= 0;
};

export const isValidSamplesFormat = (samples: string): boolean => {
  // Format: "0-0-0" (three numbers separated by dashes)
  const pattern = /^\d+-\d+-\d+$/;
  return pattern.test(samples);
};

// Map enum NAME (from API/PCAP) to enum VALUE used in form Selects
export function mapPcapEnumsToFormValues(traps: any[]): SNMPTrap[] {
  if (!Array.isArray(traps)) return [];

  return traps.map((t: any) => {
    const mapped: any = { ...t };

    // Helper to map if key exists in enum
    const mapIfExists = (enumObj: any, key: any) => {
      if (!key && key !== 0) return key;
      if (typeof key !== 'string') return key;
      // Some APIs may provide enum names in uppercase or mixed; try exact match first
      if (enumObj && Object.prototype.hasOwnProperty.call(enumObj, key)) {
        return enumObj[key];
      }
      // Also try converting from uppercase with underscores to enum key
      const altKey = key.toUpperCase();
      if (enumObj && Object.prototype.hasOwnProperty.call(enumObj, altKey)) {
        return enumObj[altKey];
      }
      // Fallback: return original key
      return key;
    };

    try {
      mapped.attackCategory = mapIfExists(AttackCategory, t.attackCategory);
      mapped.protocol = mapIfExists(AttackProtocol, t.protocol);
      mapped.status = mapIfExists(AttackStatus, t.status);
      mapped.risk = mapIfExists(AttackRisk, t.risk);
      mapped.action = mapIfExists(AttackAction, t.action);
      mapped.direction = mapIfExists(AttackDirection, t.direction);
    } catch (e) {
      // In case of any unexpected mapping error, leave original values
    }

    return mapped as SNMPTrap;
  });
}
