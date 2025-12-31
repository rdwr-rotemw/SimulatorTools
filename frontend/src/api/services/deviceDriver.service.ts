import apiClient from '../client';

export interface DeviceDriver {
  filename: string;
  device_type: string;
  device_version: string;
  dd_version: string;
}

export interface DeploymentResult {
  filename: string;
  success: boolean;
  message: string;
}

export interface DeploymentSummary {
  total: number;
  succeeded: number;
  failed: number;
  results: DeploymentResult[];
}

export const deviceDriverService = {
  /**
   * List all available device drivers
   */
  async listDrivers(ccIp: string): Promise<DeviceDriver[]> {
    const response = await apiClient.get(`/cc/${ccIp}/device-drivers`);
    return response.data.drivers || [];
  },

  /**
   * Upload a new device driver JAR file
   */
  async uploadDriver(ccIp: string, file: File): Promise<{ message: string; filename: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post(`/cc/${ccIp}/device-drivers/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  },

  /**
   * Deploy selected device drivers to CyberController
   */
  async deployDrivers(ccIp: string, driverFilenames: string[]): Promise<DeploymentSummary> {
    const response = await apiClient.post(`/cc/${ccIp}/device-drivers/deploy`, {
      driver_filenames: driverFilenames,
    }, {
      timeout: 600000, // 10 minutes - allows multiple drivers at 2min each
    });

    return response.data;
  },

  /**
   * Find matching driver for device type and version
   */
  async matchDriver(ccIp: string, deviceType: string, deviceVersion: string): Promise<string | null> {
    const response = await apiClient.get(`/cc/${ccIp}/device-drivers/match`, {
      params: {
        device_type: deviceType,
        device_version: deviceVersion,
      },
    });

    return response.data.matched ? response.data.filename : null;
  },
};
