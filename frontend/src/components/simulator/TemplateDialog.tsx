import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Checkbox,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { DeviceTemplate, DeviceTemplateCreate, DeviceTemplateUpdate } from '../../types/template.types';
import apiClient from '../../api/client';

interface TemplateDialogProps {
  open: boolean;
  template: DeviceTemplate | null;
  onClose: () => void;
  onSubmit: (data: DeviceTemplateCreate | DeviceTemplateUpdate) => Promise<void>;
}

interface FieldState {
  enabled: boolean;
  value: string;
}

type FieldStates = Record<string, FieldState>;

const defaultFieldValues: Record<string, string> = {
  // DeviceMap
  'device_map.release': '11.0',
  'device_map.description': '',
  'device_map.user_data': '',
  'device_map.setup_file': '',
  'device_map.interface': '',
  'device_map.separator': '',
  'device_map.start_interface_num': '0',
  'device_map.username': '',

  // General
  'general.name': '<ip>',
  'general.multi_home': '1',
  'general.dhcp': '0',
  'general.subnet_mask': '255.255.255.0',
  'general.mac_address': '',
  'general.interface': '',
  'general.user_data': '',
  'general.topology_data': '',
  'general.display_tag': '',
  'general.modeling_file': '/opt/sapro/tcl/varchange.tcl',
  'general.common_data_file': '',

  // SNMP
  'snmp.read_community': 'public',
  'snmp.write_community': 'public',
  'snmp.mib_file': '/opt/sapro/cmf/DP_10_6.cmf',
  'snmp.agent_file': '/opt/sapro/var/DPX_10-6.var',
  'snmp.trap_mgr': '',
  'snmp.snmp_str': 'V1V2V3',
  'snmp.response_delay': '0',
  'snmp.mtu_size': '1500',
  'snmp.snmp_port': '161',
  'snmp.security_level': 'NoAuthNoPriv',
  'snmp.user_name': 'noAuthUser',

  // SOAP
  'soap.soap_http_port': '80',
  'soap.soap_https_port': '443',
  'soap.xml_https_type': '2',
  'soap.soap_mod_file': '',
  'soap.soap_content_type': '',

  // SSH
  'ssh.ssh_user_name': 'radware',
  'ssh.ssh_password': 'radware1',
  'ssh.ssh_scp_base_dir': '/tmp',
  'ssh.ssh_version': 'SSH-1.99-SSHSAPRO-4.3',
  'ssh.ssh_file': '/opt/sapro/telnet/DPX_2.tel',
};

export const TemplateDialog: React.FC<TemplateDialogProps> = ({ open, template, onClose, onSubmit }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [fields, setFields] = useState<FieldStates>({});

  // File lists state
  const [fileListsLoading, setFileListsLoading] = useState(false);
  const [isFilesLoaded, setIsFilesLoaded] = useState(false);
  const [fileLists, setFileLists] = useState<{
    mib: string[];
    agent: string[];
    ssh: string[];
    soap: string[];
    modeling: string[];
  }>({
    mib: [],
    agent: [],
    ssh: [],
    soap: [],
    modeling: [],
  });

  const [sectionEnabled, setSectionEnabled] = useState<Record<string, boolean>>({
    soap: true,
    ssh: true,
  });

  const isEditMode = !!template;

  // Helper function to extract filename from full path
  const extractFilename = (fullPath: string | null | undefined): string => {
    if (!fullPath || typeof fullPath !== 'string') {
      return '';
    }
    const parts = fullPath.split('/');
    return parts[parts.length - 1] || '';
  };

  // Initialize field states - Create mode (immediate, no file dependency)
  useEffect(() => {
    if (open && !template) {
      // Create mode: reset form with all default fields pre-enabled
      setName('');
      setDescription('');
      setSectionEnabled({ soap: true, ssh: true });
      const initialFields: FieldStates = {};
      Object.entries(defaultFieldValues).forEach(([path, value]) => {
        initialFields[path] = { enabled: true, value };
      });
      setFields(initialFields);
    }
  }, [open, template]);

  // Initialize field states - Edit mode (waits for files to load)
  useEffect(() => {
    if (open && template && isFilesLoaded) {
      // Edit mode: load existing template data AFTER files are loaded
      console.log('Loading template for edit (files loaded):', template);

      // Validate template structure
      if (!template.template || typeof template.template !== 'object') {
        console.error('Invalid template structure:', template);
        return;
      }

      setName(template.name);
      setDescription(template.description || '');

      const deviceMap = template.template?.device_map;
      const device = deviceMap?.device;
      setSectionEnabled({
        soap: !!device?.soap && Object.keys(device.soap).length > 0,
        ssh: !!device?.ssh && Object.keys(device.ssh).length > 0,
      });

      const newFields: FieldStates = {};

      // Helper to add field if it exists
      const addField = (path: string, value: any) => {
        // Only add primitive values (string, number, boolean)
        // Skip objects, arrays, null, undefined
        if (value !== undefined && value !== null && value !== '') {
          const valueType = typeof value;
          if (valueType === 'string' || valueType === 'number' || valueType === 'boolean') {
            newFields[path] = { enabled: true, value: String(value) };
          } else {
            console.warn(`Skipping non-primitive value for ${path}:`, value);
          }
        }
      };

      // DeviceMap fields
      if (deviceMap) {
        addField('device_map.release', deviceMap.release);
        addField('device_map.description', deviceMap.description);
        addField('device_map.user_data', deviceMap.user_data);
        addField('device_map.setup_file', deviceMap.setup_file);
        addField('device_map.interface', deviceMap.interface);
        addField('device_map.separator', deviceMap.separator);
        addField('device_map.start_interface_num', deviceMap.start_interface_num);
        addField('device_map.username', deviceMap.username);
      }

      // General fields
      if (device?.general) {
        Object.entries(device.general).forEach(([key, value]) => {
          addField(`general.${key}`, value);
        });
      }

      // SNMP fields
      if (device?.snmp) {
        Object.entries(device.snmp).forEach(([key, value]) => {
          addField(`snmp.${key}`, value);
        });
      }

      // SOAP fields
      if (device?.soap) {
        Object.entries(device.soap).forEach(([key, value]) => {
          addField(`soap.${key}`, value);
        });
      }

      // SSH fields
      if (device?.ssh) {
        Object.entries(device.ssh).forEach(([key, value]) => {
          addField(`ssh.${key}`, value);
        });
      }

      setFields(newFields);
      console.log('Template fields populated:', Object.keys(newFields).length, 'fields');
    }
  }, [open, template, isFilesLoaded]);

  // Load file lists from Sapro server when dialog opens
  useEffect(() => {
    if (open) {
      // Reset isFilesLoaded flag when dialog opens
      setIsFilesLoaded(false);
      // Load files if not already loaded
      if (fileLists.mib.length === 0) {
        loadFileLists();
      } else {
        // If files already loaded, mark as ready
        setIsFilesLoaded(true);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const loadFileLists = async () => {
    setFileListsLoading(true);
    setIsFilesLoaded(false);
    try {
      // Fetch all file types in parallel
      const [mibRes, agentRes, sshRes, soapRes, modelingRes] = await Promise.all([
        apiClient.get('/sapro-files/mib'),
        apiClient.get('/sapro-files/agent'),
        apiClient.get('/sapro-files/ssh'),
        apiClient.get('/sapro-files/soap'),
        apiClient.get('/sapro-files/modeling'),
      ]);

      // Helper to ensure we only get string arrays
      const ensureStringArray = (data: any): string[] => {
        if (!data || !data.files || !Array.isArray(data.files)) {
          return [];
        }
        return data.files.filter((f: any) => typeof f === 'string');
      };

      setFileLists({
        mib: ensureStringArray(mibRes.data),
        agent: ensureStringArray(agentRes.data),
        ssh: ensureStringArray(sshRes.data),
        soap: ensureStringArray(soapRes.data),
        modeling: ensureStringArray(modelingRes.data),
      });

      // Mark files as loaded - allows form population to proceed
      setIsFilesLoaded(true);
    } catch (err) {
      console.error('Failed to load file lists:', err);
      // Set empty arrays on error so we don't keep retrying
      setFileLists({
        mib: [],
        agent: [],
        ssh: [],
        soap: [],
        modeling: [],
      });
      // Mark as loaded even on error to allow form to proceed
      setIsFilesLoaded(true);
    } finally {
      setFileListsLoading(false);
    }
  };

  const handleSectionToggle = (section: string) => {
    setSectionEnabled(prev => {
      const nowEnabled = !prev[section];
      // Disable/enable all fields in this section
      setFields(prevFields => {
        const updated = { ...prevFields };
        Object.keys(updated).forEach(path => {
          if (path.startsWith(`${section}.`)) {
            updated[path] = { ...updated[path], enabled: nowEnabled };
          }
        });
        return updated;
      });
      return { ...prev, [section]: nowEnabled };
    });
  };

  const handleFieldToggle = (fieldPath: string) => {
    setFields(prev => {
      const isCurrentlyEnabled = prev[fieldPath]?.enabled || false;
      return {
        ...prev,
        [fieldPath]: {
          enabled: !isCurrentlyEnabled,
          value: prev[fieldPath]?.value || defaultFieldValues[fieldPath] || '',
        },
      };
    });
  };

  const handleFieldValueChange = (fieldPath: string, value: string) => {
    setFields(prev => ({
      ...prev,
      [fieldPath]: {
        ...prev[fieldPath],
        value,
      },
    }));
  };

  const buildTemplateStructure = () => {
    const template: any = {
      device_map: {}
    };

    // Add ALL device_map level fields (SAPRO requires all attributes, even empty)
    Object.entries(defaultFieldValues).forEach(([path]) => {
      const parts = path.split('.');
      if (parts[0] === 'device_map' && parts.length === 2) {
        const state = fields[path];
        template.device_map[parts[1]] = state?.value ?? defaultFieldValues[path] ?? '';
      }
    });

    template.device_map.device = {};

    // Add device sub-sections — include ALL fields for active sections
    // SAPRO requires every attribute present, even with empty values
    ['general', 'snmp', 'soap', 'ssh'].forEach(section => {
      // Skip optional sections that are toggled off
      if (section in sectionEnabled && !sectionEnabled[section]) return;

      template.device_map.device[section] = {};
      Object.entries(defaultFieldValues).forEach(([path]) => {
        if (path.startsWith(`${section}.`)) {
          const fieldName = path.split('.')[1];
          const state = fields[path];
          template.device_map.device[section][fieldName] = state?.value ?? defaultFieldValues[path] ?? '';
        }
      });
    });

    return template;
  };

  const handleSubmit = async () => {
    if (!name.trim() && !isEditMode) {
      return; // Name required for new templates
    }

    setIsLoading(true);
    try {
      const templateStructure = buildTemplateStructure();

      if (isEditMode) {
        const updateData: DeviceTemplateUpdate = {
          name: template?.name,  // Always include current template name
          description,
          template: templateStructure,
        };
        await onSubmit(updateData);
      } else {
        const createData: DeviceTemplateCreate = {
          name: name.trim(),
          description: description.trim(),
          template: templateStructure,
        };
        await onSubmit(createData);
      }

      onClose();
    } catch (err: any) {
      console.error('Template submit failed', err);

      // Extract meaningful error message
      let errorMsg = 'Failed to save template';
      if (err?.response?.status === 422 && err?.response?.data?.detail) {
        // Handle Pydantic validation errors
        const details = err.response.data.detail;
        if (Array.isArray(details) && details.length > 0) {
          // Extract first validation error: "field: message"
          errorMsg = `${details[0].loc[1]}: ${details[0].msg}`;
        } else if (typeof details === 'string') {
          errorMsg = details;
        }
      } else if (err?.message) {
        errorMsg = err.message;
      }

      console.error('Error message:', errorMsg);
      // TODO: Show error to user via snackbar or alert
      // For now, just log it
      alert(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const renderField = (label: string, fieldPath: string, helperText?: string) => {
    const state = fields[fieldPath] || { enabled: false, value: defaultFieldValues[fieldPath] || '' };

    // Ensure value is always a string
    const fieldValue = typeof state.value === 'string' ? state.value : String(state.value || '');

    return (
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={state.enabled}
              onChange={() => handleFieldToggle(fieldPath)}
              size="small"
            />
          }
          label=""
          sx={{ m: 0 }}
        />
        <TextField
          label={label}
          fullWidth
          size="small"
          disabled={!state.enabled}
          value={fieldValue}
          onChange={(e) => handleFieldValueChange(fieldPath, e.target.value)}
          helperText={typeof helperText === 'string' ? helperText : undefined}
          sx={{
            '& .MuiInputBase-input.Mui-disabled': {
              backgroundColor: '#f5f5f5',
            },
          }}
        />
      </Box>
    );
  };

  const renderDropdownField = (
    label: string,
    fieldPath: string,
    fileType: 'mib' | 'agent' | 'ssh' | 'soap' | 'modeling',
    helperText?: string
  ) => {
    const state = fields[fieldPath] || { enabled: false, value: defaultFieldValues[fieldPath] || '' };
    const files = fileLists[fileType] || [];

    // Extract filename from full path using helper
    const currentValue = extractFilename(state.value);

    // Check if current file exists in the list
    const fileExistsInList = currentValue && files.includes(currentValue);

    // If file doesn't exist in list and we have a value, allow manual entry
    const useTextInput = state.enabled && currentValue && !fileExistsInList && !fileListsLoading;

    return (
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={state.enabled}
              onChange={() => handleFieldToggle(fieldPath)}
              size="small"
            />
          }
          label=""
          sx={{ m: 0 }}
        />
        {useTextInput ? (
          // Fallback: Show text input if file not in list
          <TextField
            label={label}
            fullWidth
            size="small"
            value={state.value}
            onChange={(e) => handleFieldValueChange(fieldPath, e.target.value)}
            helperText={`File not found in list. Manual entry: ${state.value}`}
            sx={{
              '& .MuiInputBase-input': {
                backgroundColor: '#FFF3E0',
              },
            }}
          />
        ) : (
          // Default: Show dropdown
          <FormControl
            fullWidth
            size="small"
            disabled={!state.enabled || fileListsLoading}
            sx={{
              '& .MuiInputBase-root.Mui-disabled': {
                backgroundColor: '#f5f5f5',
              },
            }}
          >
            <InputLabel>{label}</InputLabel>
            <Select
              value={currentValue}
              label={label}
              onChange={(e) => {
                const filename = e.target.value;
                // Construct full path based on file type
                const pathMap: Record<string, string> = {
                  mib: '/opt/sapro/cmf/',
                  agent: '/opt/sapro/var/',
                  ssh: '/opt/sapro/telnet/',
                  soap: '/opt/sapro/xml/',
                  modeling: '/opt/sapro/tcl/',
                };
                const fullPath = filename ? `${pathMap[fileType]}${filename}` : '';
                handleFieldValueChange(fieldPath, fullPath);
              }}
            >
              <MenuItem value="">
                <em>{fileListsLoading ? 'Loading...' : 'None'}</em>
              </MenuItem>
              {files.filter(f => typeof f === 'string').map((file) => (
                <MenuItem key={file} value={file}>
                  {String(file)}
                </MenuItem>
              ))}
            </Select>
            {helperText && typeof helperText === 'string' && (
              <Typography variant="caption" sx={{ mt: 0.5, color: 'text.secondary' }}>
                {helperText}
              </Typography>
            )}
          </FormControl>
        )}
      </Box>
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            margin: '32px',
            maxHeight: 'calc(100% - 64px)',
          }
        }
      }}
    >
      <DialogTitle>
        {isEditMode ? `Edit Template: ${template?.name}` : 'Create New Template'}
      </DialogTitle>

      <DialogContent sx={{ paddingTop: '24px !important' }}>
        <Box sx={{ mb: 3 }}>
          <TextField
            label="Template Name"
            fullWidth
            required={!isEditMode}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isEditMode}
            sx={{ mb: 2 }}
            helperText={isEditMode ? 'Template name cannot be changed' : 'Unique identifier for this template'}
          />

          <TextField
            label="Description"
            fullWidth
            multiline
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            helperText="Brief description of this device template"
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        <Typography variant="subtitle2" sx={{ mb: 2, color: 'text.secondary' }}>
          Template Structure (check to enable field)
        </Typography>

        {/* DeviceMap Level */}
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" fontWeight="medium">Device Map</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {renderField('Release', 'device_map.release', 'e.g., 11.0')}
            {renderField('Description', 'device_map.description')}
            {renderField('User Data', 'device_map.user_data')}
            {renderField('Setup File', 'device_map.setup_file')}
            {renderField('Interface', 'device_map.interface')}
            {renderField('Separator', 'device_map.separator')}
            {renderField('Start Interface Num', 'device_map.start_interface_num', 'e.g., 0')}
            {renderField('Username', 'device_map.username')}
          </AccordionDetails>
        </Accordion>

        {/* General */}
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" fontWeight="medium">General</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {/* Name field removed - it's the device IP address, set elsewhere */}
            {renderField('Multi Home', 'general.multi_home', 'e.g., 1')}
            {renderField('DHCP', 'general.dhcp', 'e.g., 0')}
            {renderField('Subnet Mask', 'general.subnet_mask', 'e.g., 255.255.255.0')}
            {renderField('MAC Address', 'general.mac_address')}
            {renderField('Interface', 'general.interface')}
            {renderField('User Data', 'general.user_data')}
            {renderField('Topology Data', 'general.topology_data')}
            {renderField('Display Tag', 'general.display_tag')}
            {renderDropdownField('Modeling File', 'general.modeling_file', 'modeling', 'Select .tcl file from /opt/sapro/tcl/')}
            {renderField('Common Data File', 'general.common_data_file')}
          </AccordionDetails>
        </Accordion>

        {/* SNMP */}
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" fontWeight="medium">SNMP</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {renderField('Read Community', 'snmp.read_community', 'e.g., public')}
            {renderField('Write Community', 'snmp.write_community', 'e.g., public')}
            {renderDropdownField('MIB File', 'snmp.mib_file', 'mib', 'Select .cmf file from /opt/sapro/cmf/')}
            {renderDropdownField('Agent File', 'snmp.agent_file', 'agent', 'Select .var/.cva file from /opt/sapro/var/')}
            {renderField('Trap Manager', 'snmp.trap_mgr')}
            {renderField('SNMP String', 'snmp.snmp_str', 'e.g., V1V2V3')}
            {renderField('Response Delay', 'snmp.response_delay', 'e.g., 0')}
            {renderField('MTU Size', 'snmp.mtu_size', 'e.g., 1500')}
            {renderField('SNMP Port', 'snmp.snmp_port', 'e.g., 161')}
            {renderField('Security Level', 'snmp.security_level', 'e.g., NoAuthNoPriv')}
            {renderField('User Name', 'snmp.user_name', 'e.g., noAuthUser')}
          </AccordionDetails>
        </Accordion>

        {/* SOAP */}
        <Accordion disabled={!sectionEnabled.soap}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={sectionEnabled.soap}
                    onChange={(e) => {
                      e.stopPropagation();
                      handleSectionToggle('soap');
                    }}
                    onClick={(e) => e.stopPropagation()}
                    size="small"
                  />
                }
                label=""
                sx={{ m: 0, mr: 1 }}
              />
              <Typography variant="subtitle1" fontWeight="medium">
                SOAP {!sectionEnabled.soap && '(disabled)'}
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {renderField('SOAP HTTP Port', 'soap.soap_http_port', 'e.g., 80')}
            {renderField('SOAP HTTPS Port', 'soap.soap_https_port', 'e.g., 443')}
            {renderField('XML HTTPS Type', 'soap.xml_https_type', 'e.g., 2')}
            {renderDropdownField('SOAP Mod File', 'soap.soap_mod_file', 'soap', 'Select .xmf file from /opt/sapro/xml/')}
            {renderField('SOAP Content Type', 'soap.soap_content_type')}
          </AccordionDetails>
        </Accordion>

        {/* SSH */}
        <Accordion disabled={!sectionEnabled.ssh}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={sectionEnabled.ssh}
                    onChange={(e) => {
                      e.stopPropagation();
                      handleSectionToggle('ssh');
                    }}
                    onClick={(e) => e.stopPropagation()}
                    size="small"
                  />
                }
                label=""
                sx={{ m: 0, mr: 1 }}
              />
              <Typography variant="subtitle1" fontWeight="medium">
                SSH {!sectionEnabled.ssh && '(disabled)'}
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {renderField('SSH User Name', 'ssh.ssh_user_name', 'Default: radware')}
            {renderField('SSH Password', 'ssh.ssh_password', 'Default: radware1')}
            {renderField('SSH SCP Base Dir', 'ssh.ssh_scp_base_dir', 'e.g., /tmp')}
            {renderField('SSH Version', 'ssh.ssh_version', 'e.g., SSH-1.99-SSHSAPRO-4.3')}
            {renderDropdownField('SSH File', 'ssh.ssh_file', 'ssh', 'Select .tel file from /opt/sapro/telnet/')}
          </AccordionDetails>
        </Accordion>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={isLoading || (!isEditMode && !name.trim())}
        >
          {isLoading ? <CircularProgress size={20} /> : (isEditMode ? 'Update' : 'Create')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TemplateDialog;

