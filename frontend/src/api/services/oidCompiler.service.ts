import apiClient from '../client';

export interface CompilationResult {
  success: boolean;
  cmf_path: string | null;
  var_path: string | null;
  version: string;
  stats: Record<string, number>;
  warnings: string[];
  errors: string[];
}

export interface CustomSettings {
  deviceName: string;
  platform: string;
  dataPorts: number;
  mgmtPorts: number;
}

export const compileMibs = async (
  mibZip: File,
  oidsPdf: File,
  outputName?: string,
  deviceDriverName?: string,
  deviceDriverFile?: File,
  customSettings?: CustomSettings,
): Promise<CompilationResult> => {
  const formData = new FormData();
  formData.append('mib_zip', mibZip);
  formData.append('oids_pdf', oidsPdf);
  if (outputName) formData.append('output_name', outputName);
  if (deviceDriverName) formData.append('device_driver_name', deviceDriverName);
  if (deviceDriverFile) formData.append('device_driver_file', deviceDriverFile);
  if (customSettings) {
    formData.append('device_name', customSettings.deviceName);
    formData.append('platform', customSettings.platform);
    formData.append('data_ports', String(customSettings.dataPorts));
    formData.append('mgmt_ports', String(customSettings.mgmtPorts));
  }

  const response = await apiClient.post<CompilationResult>(
    '/oid-compiler/compile',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600000 }
  );
  return response.data;
};

export const listDeviceDrivers = async (): Promise<string[]> => {
  const response = await apiClient.get('/oid-compiler/device-drivers');
  return response.data.drivers || [];
};

export const checkHealth = async (): Promise<{ status: string; module: string }> => {
  const response = await apiClient.get('/oid-compiler/health');
  return response.data;
};
