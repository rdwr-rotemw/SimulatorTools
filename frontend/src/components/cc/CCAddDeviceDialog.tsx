import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Alert,
  CircularProgress,
  Box,
  Tooltip,
  Autocomplete,
  Typography,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { HelpOutline } from '@mui/icons-material';
import { useForm, Controller } from 'react-hook-form';
import { CCAddDeviceRequest } from '../../types/cc.types';
import useCCStore from '../../store/ccStore';
import { Simulator } from '../../types/simulator.types';

interface CCAddDeviceDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CCAddDeviceRequest, autoInstallDriver: boolean) => Promise<void>;
  ccIp: string;
}

export const CCAddDeviceDialog: React.FC<CCAddDeviceDialogProps> = ({ open, onClose, onSubmit, ccIp }) => {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    control,
  } = useForm<CCAddDeviceRequest>({
    defaultValues: {
      name: '',
      type: '',
      cli_username: 'radware',
      cli_password: 'radware1',
      http_username: 'radware',
      https_password: 'radware1',
      management_ip: '',
      vision_mgt_port: '',
      register_device_events: false,
    },
  });

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [managementIPError, setManagementIPError] = useState<string | null>(null);
  const [lastProcessedValue, setLastProcessedValue] = useState('');
  const [autoInstallDriver, setAutoInstallDriver] = useState(true); // Default to enabled

  // Get management ports from CC store
  const managementPorts = useCCStore((state) => state.managementPorts);

  // Get Sapro simulators from CC store (already loaded and cached in session storage!)
  const saproSimulators = useCCStore((state) => state.saproSimulators);

  // Helper to parse IP to numeric array for comparison
  const parseIP = (ip: string): number[] => {
    return ip.split('.').map(Number);
  };

  // Helper to generate all IPs in range
  const generateIPRange = (startIP: string, endIP: string): string[] => {
    const start = parseIP(startIP);
    const end = parseIP(endIP);

    const ips: string[] = [];
    const current = [...start];

    while (true) {
      ips.push(current.join('.'));

      // Check if reached end
      if (current.every((val, idx) => val === end[idx])) break;

      // Increment IP
      for (let i = 3; i >= 0; i--) {
        if (current[i] < 255) {
          current[i]++;
          break;
        } else {
          current[i] = 0;
        }
      }

      // Safety: max 254 IPs
      if (ips.length > 254) break;
    }

    return ips;
  };

  // Validate IP range against Sapro simulators
  const validateIPRange = (value: string): string | true => {
    if (!value || value.trim() === '') {
      return 'Management IP is required';
    }

    const trimmedValue = value.trim();
    const saproIPSet = new Set(saproSimulators.map((sim: Simulator) => sim.ip_address));

    // Check if it's a range
    if (trimmedValue.includes('-')) {
      const [startIP, endIP] = trimmedValue.split('-').map(s => s.trim());

      // Validate IP format
      const ipv4Regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

      if (!ipv4Regex.test(startIP) || !ipv4Regex.test(endIP)) {
        return 'Invalid IP range format';
      }

      // Generate all IPs in range
      const rangeIPs = generateIPRange(startIP, endIP);

      if (rangeIPs.length > 254) {
        return 'Range too large (max 254 IPs)';
      }

      // Check if all IPs exist in Sapro
      const missingIPs = rangeIPs.filter(ip => !saproIPSet.has(ip));

      if (missingIPs.length > 0) {
        if (missingIPs.length <= 5) {
          return `Missing simulators in Sapro: ${missingIPs.join(', ')}`;
        } else {
          return `${missingIPs.length} simulators in this range don't exist in Sapro`;
        }
      }

      return true;
    } else {
      // Single IP
      const ipv4Regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

      if (!ipv4Regex.test(trimmedValue)) {
        return 'Invalid IP format';
      }

      // Check if IP exists in Sapro
      if (!saproIPSet.has(trimmedValue)) {
        return 'Simulator does not exist in Sapro';
      }

      return true;
    }
  };

  // Get filtered autocomplete options based on current input
  const getFilteredOptions = (inputValue: string): string[] => {
    // Check if user is typing a range
    if (inputValue.includes('-')) {
      const parts = inputValue.split('-');
      const startIP = parts[0].trim();
      const endPart = parts[1]?.trim() || '';

      // Validate start IP
      const ipv4Regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

      if (ipv4Regex.test(startIP)) {
        // Extract subnet and last octet from start IP
        const startOctets = startIP.split('.').map(Number);
        const startLastOctet = startOctets[3];
        const subnet = startOctets.slice(0, 3).join('.');

        // Filter IPs in same subnet with last octet > start
        let filtered = saproSimulators
          .map((sim: Simulator) => sim.ip_address)
          .filter(ip => {
            if (!ip.startsWith(subnet + '.')) return false;

            const lastOctet = parseInt(ip.split('.')[3]);
            return lastOctet > startLastOctet;
          });

        // Further filter by what user is typing after dash
        if (endPart.length > 0) {
          filtered = filtered.filter(ip => ip.startsWith(endPart));
        }

        // Sort by last octet
        return filtered.sort((a, b) => {
          const aLast = parseInt(a.split('.')[3]);
          const bLast = parseInt(b.split('.')[3]);
          return aLast - bLast;
        });
      }
    }

    // Normal case: show all simulators, filter by input
    const allIPs = saproSimulators.map((sim: Simulator) => sim.ip_address);

    if (inputValue.length > 0) {
      return allIPs.filter(ip => ip.startsWith(inputValue));
    }

    return allIPs;
  };

  // Process range input for smart subnet completion
  const processRangeInput = (value: string, previousValue: string): string => {
    // Smart range completion: ONLY if user just added a dash (transition from no-dash to dash)
    const hadDash = previousValue.includes('-');
    const hasDash = value.includes('-');
    const justAddedDash = !hadDash && hasDash;

    if (justAddedDash) {
      const parts = value.split('-');
      const startIP = parts[0].trim();
      const endPart = parts[1] || '';

      // If start IP is valid and end part is empty, auto-complete subnet
      const ipv4Regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

      if (ipv4Regex.test(startIP) && endPart.length === 0) {
        // Extract subnet (first 3 octets)
        const subnet = startIP.split('.').slice(0, 3).join('.');
        return `${startIP}-${subnet}.`;
      }
    }

    return value;
  };

  useEffect(() => {
    if (!open) {
      reset();
      setErrorMessage(null);
      setManagementIPError(null);
      setLastProcessedValue('');
      setAutoInstallDriver(true); // Reset to default
    }
  }, [open, reset]);

  const handleFormSubmit = handleSubmit(async (data: CCAddDeviceRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await onSubmit(data, autoInstallDriver);
      onClose();
      reset();
      setAutoInstallDriver(true); // Reset to default
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'An error occurred';
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      scroll="body"
      sx={{ m: '32px' }}
    >
      <DialogTitle>Add Device to CyberController</DialogTitle>

      <DialogContent sx={{ pt: '32px', pb: '24px' }}>
        {errorMessage && (
          <Box mb={2}>
            <Alert severity="error">{errorMessage}</Alert>
          </Box>
        )}

        <form id="cc-add-device-form" onSubmit={handleFormSubmit}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 2,
              rowGap: 3,
              mt: 3,
            }}
          >
            {/* Device Name */}
            <TextField
              label="Device Name"
              fullWidth
              size="small"
              {...register('name', { required: 'Device name is required' })}
              error={!!errors.name}
              helperText={errors.name?.message as string}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* Device Type */}
            <TextField
              label="Device Type"
              select
              fullWidth
              size="small"
              defaultValue=""
              {...register('type', { required: 'Device type is required' })}
              error={!!errors.type}
              helperText={errors.type?.message as string}
              sx={{ '& label': { fontSize: '14px' } }}
            >
              <MenuItem value="DefensePro">DefensePro</MenuItem>
              <MenuItem value="Alteon">Alteon</MenuItem>
            </TextField>

            {/* Management IP - Hybrid Autocomplete + Free Text */}
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
              <Box sx={{ flex: 1 }}>
                <Controller
                  name="management_ip"
                  control={control}
                  rules={{
                    required: 'Management IP is required',
                    validate: validateIPRange
                  }}
                  render={({ field }) => (
                    <Autocomplete
                      freeSolo
                      options={getFilteredOptions(field.value || '')}
                      value={field.value || ''}
                      inputValue={field.value || ''}
                      onChange={(_, newValue) => {
                        if (!newValue) {
                          field.onChange('');
                          setLastProcessedValue('');
                          setManagementIPError(null);
                          return;
                        }

                        // If current value has a dash (range in progress), preserve start IP
                        const currentValue = field.value || '';
                        let finalValue = newValue;

                        if (currentValue.includes('-')) {
                          // Extract start IP from current value
                          const startIP = currentValue.split('-')[0].trim();

                          // Check if selected value is just an IP (not a full range)
                          const ipv4Regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

                          const isValidIP = ipv4Regex.test(newValue);
                          const hasNoDash = !newValue.includes('-');

                          if (isValidIP && hasNoDash) {
                            // User selected an end IP from dropdown - combine with start IP
                            finalValue = `${startIP}-${newValue}`;
                          }
                        }

                        field.onChange(finalValue);
                        setLastProcessedValue(finalValue);

                        const validationResult = validateIPRange(finalValue);
                        setManagementIPError(validationResult === true ? null : validationResult);
                      }}
                      onInputChange={(_, newInputValue, reason) => {
                        // Don't process if user selected from dropdown - onChange will handle it
                        if (reason === 'reset' || reason === 'selectOption') {
                          return;
                        }

                        const processedValue = processRangeInput(newInputValue, lastProcessedValue);
                        field.onChange(processedValue);
                        setLastProcessedValue(processedValue);

                        const validationResult = validateIPRange(processedValue);
                        setManagementIPError(validationResult === true ? null : validationResult);
                      }}
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          label="Management IP"
                          size="small"
                          error={!!managementIPError}
                          helperText={
                            managementIPError ||
                            (field.value && validateIPRange(field.value) === true
                              ? ''
                              : 'Select from dropdown or type range (auto-completes subnet)')
                          }
                          placeholder="Select or paste IP/Range"
                          sx={{ '& label': { fontSize: '14px' } }}
                        />
                      )}
                      renderOption={(props, option) => {
                        const simulator = saproSimulators.find((sim: Simulator) => sim.ip_address === option);
                        return (
                          <li {...props} key={option}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                              <Typography variant="body2" fontWeight={500}>{option}</Typography>
                              {simulator && (
                                <Typography variant="caption" color="text.secondary">
                                  {simulator.type} {simulator.version ? `(${simulator.version})` : ''} - Map: {simulator.map}
                                </Typography>
                              )}
                            </Box>
                          </li>
                        );
                      }}
                      filterOptions={(options) => options}
                      disabled={saproSimulators.length === 0}
                      loading={saproSimulators.length === 0}
                      sx={{ '& label': { fontSize: '14px' } }}
                    />
                  )}
                />
              </Box>

              <Tooltip
                title={
                  <Box sx={{ whiteSpace: 'pre-line', fontSize: '12px', p: 0.5 }}>
                    {'Supported formats:\n\n• Single IP: 50.50.10.1\n• IP Range: 50.50.10.1-50.50.10.50\n\nYou can:\n• Select single IP from dropdown\n• Paste range directly (e.g., 50.50.10.1-50.50.10.50)\n\nAll IPs must exist in Sapro simulators.'}
                  </Box>
                }
                placement="right"
                arrow
              >
                <HelpOutline
                  sx={{
                    fontSize: 18,
                    color: 'text.secondary',
                    cursor: 'help',
                    flexShrink: 0,
                    mt: 0.5
                  }}
                />
              </Tooltip>
            </Box>

            {/* Vision Management Port */}
            <TextField
              label="Vision Management Port"
              select
              fullWidth
              size="small"
              defaultValue=""
              {...register('vision_mgt_port', { required: 'Vision management port is required' })}
              error={!!errors.vision_mgt_port}
              helperText={errors.vision_mgt_port?.message as string}
              disabled={managementPorts.length === 0}
              sx={{ '& label': { fontSize: '14px' } }}
            >
              {managementPorts.length > 0 ? (
                managementPorts.map((port) => (
                  <MenuItem key={port.interface} value={port.interface}>
                    {port.interface} ({port.address})
                  </MenuItem>
                ))
              ) : (
                <MenuItem value="">No ports available</MenuItem>
              )}
            </TextField>

            {/* CLI Username */}
            <TextField
              label="CLI Username"
              fullWidth
              size="small"
              {...register('cli_username', { required: 'CLI username is required' })}
              error={!!errors.cli_username}
              helperText={errors.cli_username?.message as string}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* CLI Password */}
            <TextField
              label="CLI Password"
              type="password"
              fullWidth
              size="small"
              {...register('cli_password', { required: 'CLI password is required' })}
              error={!!errors.cli_password}
              helperText={errors.cli_password?.message as string}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* HTTP Username */}
            <TextField
              label="HTTP Username"
              fullWidth
              size="small"
              {...register('http_username', { required: 'HTTP username is required' })}
              error={!!errors.http_username}
              helperText={errors.http_username?.message as string}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* HTTPS Password */}
            <TextField
              label="HTTPS Password"
              type="password"
              fullWidth
              size="small"
              {...register('https_password', { required: 'HTTPS password is required' })}
              error={!!errors.https_password}
              helperText={errors.https_password?.message as string}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* Register Device Events */}
            <TextField
              label="Register Device Events"
              select
              fullWidth
              size="small"
              defaultValue={false}
              {...register('register_device_events')}
              sx={{ '& label': { fontSize: '14px' } }}
            >
              <MenuItem value={false as any}>False</MenuItem>
              <MenuItem value={true as any}>True</MenuItem>
            </TextField>
          </Box>

          {/* Auto Install Device Driver Checkbox */}
          <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={autoInstallDriver}
                  onChange={(e) => setAutoInstallDriver(e.target.checked)}
                />
              }
              label="Auto Install Device Driver"
            />
            <Tooltip
              title={
                <Box sx={{ whiteSpace: 'pre-line', fontSize: '12px', p: 0.5 }}>
                  {'When enabled:\n\n1. Adds devices to CyberController\n2. Gets device versions and installs matching drivers\n3. Validates devices are up\n\nIf driver not found, devices will still be added and validated.'}
                </Box>
              }
              placement="right"
              arrow
            >
              <HelpOutline
                sx={{
                  fontSize: 18,
                  color: 'text.secondary',
                  cursor: 'help',
                }}
              />
            </Tooltip>
          </Box>
        </form>
      </DialogContent>

      <DialogActions>
        <Button
          onClick={() => {
            reset();
            onClose();
          }}
          disabled={isLoading}
        >
          Cancel
        </Button>

        <Button type="submit" form="cc-add-device-form" variant="contained" disabled={isLoading}>
          {isLoading ? <CircularProgress size={20} color="inherit" /> : 'Add Device'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
