export interface CCSession {
  cc_ip: string;
  jsession_id: string;
  login_time: string;
}

export interface CCDevice {
  management_ip: string;
  name?: string;
  device_id?: string;
  device_type?: string;
  status?: string;
  version?: string;
}

export interface CCLoginRequest {
  username: string;
  password: string;
}

export interface CCLoginResponse {
  success: boolean;
  message: string;
}

export interface CCAddDeviceRequest {
  username: string;
  password: string;
  name: string;
  management_ip: string;
  device_type: string;
  device_user: string;
  device_password: string;
  parent_orm?: any;
}

export interface CCDeleteResponse {
  success: boolean;
  message: string;
}

export interface ManagementPort {
  interface: string;
  address: string;
}

export interface CCState {
  currentCC: string | null;
  devices: CCDevice[];
  managementPorts: ManagementPort[];
  isLoading: boolean;
  error: string | null;
  login: (cc_ip: string, username: string, password: string) => Promise<void>;
  logout: (cc_ip: string) => Promise<void>;
  fetchDevices: (cc_ip: string) => Promise<void>;
  fetchManagementPorts: (cc_ip: string) => Promise<void>;
  addDevice: (cc_ip: string, data: CCAddDeviceRequest) => Promise<void>;
  deleteDevice: (cc_ip: string, simulator_ip: string) => Promise<void>;
  clearError: () => void;
  clearState: () => void;
}
