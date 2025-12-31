import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Checkbox,
  FormControlLabel,
  CircularProgress,
  Alert,
  Divider,
  LinearProgress,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import InstallDesktopIcon from '@mui/icons-material/InstallDesktop';
import { deviceDriverService, DeviceDriver, DeploymentSummary } from '../../api/services/deviceDriver.service';
import { CCDevice } from '../../types/cc.types';

interface CCDeviceDriverDialogProps {
  open: boolean;
  onClose: () => void;
  ccIp: string;
  devices: CCDevice[];
}

interface UniqueDeviceVersion {
  device_type: string;
  device_version: string;
  count: number;
  matchedFilename?: string;
}

export const CCDeviceDriverDialog: React.FC<CCDeviceDriverDialogProps> = ({
  open,
  onClose,
  ccIp,
  devices,
}) => {
  const [uniqueVersions, setUniqueVersions] = useState<UniqueDeviceVersion[]>([]);
  const [selectedDrivers, setSelectedDrivers] = useState<Set<string>>(new Set());
  const [uploadedDrivers, setUploadedDrivers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeploying, setIsDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deploymentResult, setDeploymentResult] = useState<DeploymentSummary | null>(null);

  // Extract unique device type/version combinations from devices
  useEffect(() => {
    if (!open) {
      // Reset state when dialog closes
      setSelectedDrivers(new Set());
      setUploadedDrivers([]);
      setError(null);
      setDeploymentResult(null);
      return;
    }

    const extractUniqueVersions = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // 1. Get all available drivers ONCE
        const allDrivers = await deviceDriverService.listDrivers(ccIp);

        // 2. Group devices by type and version (using existing devices prop)
        const versionMap = new Map<string, UniqueDeviceVersion>();

        devices.forEach((device) => {
          if (device.device_type && device.version) {
            const key = `${device.device_type}-${device.version}`;

            if (versionMap.has(key)) {
              const existing = versionMap.get(key)!;
              existing.count += 1;
            } else {
              versionMap.set(key, {
                device_type: device.device_type,
                device_version: device.version,
                count: 1,
              });
            }
          }
        });

        // 3. Match versions to drivers in frontend (no API calls)
        const matchedVersions = Array.from(versionMap.values()).map((version) => {
          const matchedDriver = allDrivers.find(
            (driver) =>
              driver.device_type === version.device_type &&
              driver.device_version === version.device_version
          );

          return {
            ...version,
            matchedFilename: matchedDriver?.filename,
          };
        });

        // Filter out versions without matched drivers
        const availableVersions = matchedVersions.filter((v) => v.matchedFilename);

        setUniqueVersions(availableVersions);

        if (availableVersions.length === 0) {
          setError('No matching device drivers found for your devices. Please upload drivers manually.');
        }
      } catch (err) {
        console.error('Failed to load drivers:', err);
        setError('Failed to load device drivers');
      } finally {
        setIsLoading(false);
      }
    };

    extractUniqueVersions();
  }, [open, devices, ccIp]);

  const handleCheckboxChange = (filename: string, checked: boolean) => {
    const newSelected = new Set(selectedDrivers);
    if (checked) {
      newSelected.add(filename);
    } else {
      newSelected.delete(filename);
    }
    setSelectedDrivers(newSelected);
  };

  const handleImportLocal = async () => {
    // Create hidden file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.jar';
    input.multiple = false;

    input.onchange = async (e: Event) => {
      const target = e.target as HTMLInputElement;
      const file = target.files?.[0];

      if (!file) return;

      setIsLoading(true);
      setError(null);

      try {
        const result = await deviceDriverService.uploadDriver(ccIp, file);

        // Add uploaded driver to the list
        setUploadedDrivers((prev) => [...prev, result.filename]);

        // Auto-select the uploaded driver
        setSelectedDrivers((prev) => {
          const newSet = new Set(prev);
          newSet.add(result.filename);
          return newSet;
        });

        setError(null);
      } catch (err: any) {
        const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to upload driver';
        setError(errorMsg);
      } finally {
        setIsLoading(false);
      }
    };

    input.click();
  };

  const handleInstallDrivers = async () => {
    if (selectedDrivers.size === 0) return;

    setIsDeploying(true);
    setError(null);
    setDeploymentResult(null);

    try {
      const driverFilenames = Array.from(selectedDrivers);
      const result = await deviceDriverService.deployDrivers(ccIp, driverFilenames);

      setDeploymentResult(result);

      // Don't auto-close - let user close manually with Close button
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Deployment failed';
      setError(errorMsg);
    } finally {
      setIsDeploying(false);
    }
  };

  const canInstall = selectedDrivers.size > 0 && !isDeploying;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Upload Device Drivers to CyberController</DialogTitle>

      <DialogContent>
        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
            <CircularProgress />
          </Box>
        )}

        {!isLoading && error && !deploymentResult && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!isLoading && !deploymentResult && (
          <>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
              Select device drivers to install on CyberController <strong>{ccIp}</strong>
            </Typography>

            {uniqueVersions.length === 0 && uploadedDrivers.length === 0 && !error && (
              <Alert severity="info">
                No device drivers available. Upload a driver using "Import Local" button below.
              </Alert>
            )}

            {/* Existing matched drivers */}
            {uniqueVersions.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                  Available Drivers (from existing devices):
                </Typography>

                {uniqueVersions.map((version) => {
                  const filename = version.matchedFilename!;
                  const isSelected = selectedDrivers.has(filename);

                  return (
                    <FormControlLabel
                      key={filename}
                      control={
                        <Checkbox
                          checked={isSelected}
                          onChange={(e) => handleCheckboxChange(filename, e.target.checked)}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">
                            <strong>{version.device_type}</strong> - {version.device_version}
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            {filename} ({version.count} device{version.count > 1 ? 's' : ''})
                          </Typography>
                        </Box>
                      }
                    />
                  );
                })}
              </Box>
            )}

            {/* Uploaded drivers */}
            {uploadedDrivers.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                  Uploaded Drivers:
                </Typography>

                {uploadedDrivers.map((filename) => {
                  const isSelected = selectedDrivers.has(filename);

                  return (
                    <FormControlLabel
                      key={filename}
                      control={
                        <Checkbox
                          checked={isSelected}
                          onChange={(e) => handleCheckboxChange(filename, e.target.checked)}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">
                            <strong>{filename}</strong>
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            User uploaded
                          </Typography>
                        </Box>
                      }
                    />
                  );
                })}
              </Box>
            )}
          </>
        )}

        {/* Deployment progress */}
        {isDeploying && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Deploying {selectedDrivers.size} driver{selectedDrivers.size > 1 ? 's' : ''}...
            </Typography>
            <LinearProgress />
          </Box>
        )}

        {/* Deployment results */}
        {deploymentResult && (
          <Box sx={{ mb: 2 }}>
            <Alert severity={deploymentResult.failed === 0 ? 'success' : 'warning'} sx={{ mb: 2 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Deployment Complete: {deploymentResult.succeeded}/{deploymentResult.total} succeeded
              </Typography>
            </Alert>

            {deploymentResult.results.map((result) => (
              <Box
                key={result.filename}
                sx={{
                  mb: 1,
                  p: 1,
                  border: '1px solid',
                  borderColor: result.success ? '#4caf50' : '#f44336',
                  borderRadius: 1,
                  backgroundColor: result.success ? '#e8f5e9' : '#ffebee',
                }}
              >
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {result.success ? '✓' : '✗'} {result.filename}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  {result.message}
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {/* Installation warning */}
        {!deploymentResult && selectedDrivers.size > 0 && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>Note:</strong> Installation may take several minutes (approximately 2 minutes per driver).
              Please wait for the process to complete.
            </Typography>
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={isDeploying}>
          {deploymentResult ? 'Close' : 'Cancel'}
        </Button>

        {!deploymentResult && (
          <>
            <Button
              startIcon={<UploadFileIcon />}
              onClick={handleImportLocal}
              disabled={isLoading || isDeploying}
            >
              Import Local
            </Button>

            <Button
              startIcon={<InstallDesktopIcon />}
              variant="contained"
              onClick={handleInstallDrivers}
              disabled={!canInstall}
            >
              Install Drivers
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};
