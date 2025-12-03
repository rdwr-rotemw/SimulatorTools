import apiClient from '../client';
import { SNMPTrap } from '../../types/snmp.types';

export interface SNMPTemplateListItem {
  name: string;
  created_at: string;
  trap_count: number;
}

export interface SNMPTemplate {
  name: string;
  traps: SNMPTrap[];
  user_id?: number;
  cc_ip?: string;
  created_at?: string;
}

class SNMPTemplateService {
  private getBaseUrl(ccIp: string): string {
    return `/cc/${ccIp}/reporter/snmp`;
  }

  async saveTemplate(ccIp: string, name: string, traps: SNMPTrap[]): Promise<void> {
    const url = `${this.getBaseUrl(ccIp)}/templates`;
    await apiClient.post(url, { name, traps });
  }

  async listTemplates(ccIp: string): Promise<SNMPTemplateListItem[]> {
    const url = `${this.getBaseUrl(ccIp)}/templates`;
    const response = await apiClient.get<SNMPTemplateListItem[]>(url);
    return response.data;
  }

  async getTemplate(ccIp: string, templateName: string): Promise<SNMPTemplate> {
    const url = `${this.getBaseUrl(ccIp)}/templates/${encodeURIComponent(templateName)}`;
    const response = await apiClient.get<SNMPTemplate>(url);
    return response.data;
  }

  async deleteTemplate(ccIp: string, templateName: string): Promise<void> {
    const url = `${this.getBaseUrl(ccIp)}/templates/${encodeURIComponent(templateName)}`;
    await apiClient.delete(url);
  }

  async sendTraps(destinationPortIp: string, simulatorIp: string, traps: SNMPTrap[]): Promise<void> {
    const url = `/cc/${destinationPortIp}/simulators/${simulatorIp}/reporter/snmp`;
    await apiClient.post(url, { traps });
  }
}

export const snmpTemplateService = new SNMPTemplateService();
