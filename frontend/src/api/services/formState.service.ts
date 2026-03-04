import apiClient from '../client';

export interface IrpFormState {
  messages: any[] | null;
  expanded_messages: number[];
}

export interface SnmpFormState {
  traps: any[] | null;
  expanded_traps: number[];
}

export const formStateService = {
  // IRP form state
  async saveIrpFormState(ccIp: string, messages: any[], expandedMessages: number[]): Promise<void> {
    await apiClient.put(`/cc/${ccIp}/reporter/irp/form-state`, {
      messages,
      expanded_messages: expandedMessages,
    });
  },

  async loadIrpFormState(ccIp: string): Promise<{ messages: any[] | null; expandedMessages: number[] }> {
    const response = await apiClient.get<IrpFormState>(`/cc/${ccIp}/reporter/irp/form-state`);
    return {
      messages: response.data.messages,
      expandedMessages: response.data.expanded_messages,
    };
  },

  async clearIrpFormState(ccIp: string): Promise<void> {
    await apiClient.delete(`/cc/${ccIp}/reporter/irp/form-state`);
  },

  // SNMP form state
  async saveSnmpFormState(ccIp: string, traps: any[], expandedTraps: number[]): Promise<void> {
    await apiClient.put(`/cc/${ccIp}/reporter/snmp/form-state`, {
      traps,
      expanded_traps: expandedTraps,
    });
  },

  async loadSnmpFormState(ccIp: string): Promise<{ traps: any[] | null; expandedTraps: number[] }> {
    const response = await apiClient.get<SnmpFormState>(`/cc/${ccIp}/reporter/snmp/form-state`);
    return {
      traps: response.data.traps,
      expandedTraps: response.data.expanded_traps,
    };
  },

  async clearSnmpFormState(ccIp: string): Promise<void> {
    await apiClient.delete(`/cc/${ccIp}/reporter/snmp/form-state`);
  },
};
