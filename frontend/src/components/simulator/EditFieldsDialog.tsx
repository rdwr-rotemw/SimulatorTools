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
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  LinearProgress,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { Simulator } from '../../types/simulator.types';
import apiClient from '../../api/client';
import activityTracker from '../../utils/activityTracker';

interface EditFieldsDialogProps {
  open: boolean;
  simulators: Simulator[];
  onClose: () => void;
  onSuccess: () => void;
}

interface FieldState {
  enabled: boolean;
  value: string;
}

type FieldStates = Record<string, FieldState>;

type ProgressStatus = 'pending' | 'processing' | 'success' | 'failed';
interface ProgressItem {
  ip: string;
  status: ProgressStatus;
  message: string;
}

// Maps UI field path → DeviceField enum value (used by update-fields endpoint)
const fieldPathToDeviceField: Record<string, string> = {
  'general.multi_home': 'MultiHome',
  'general.dhcp': 'DHCP',
  'general.subnet_mask': 'SubnetMask',
  'general.mac_address': 'MacAddress',
  'general.interface': 'Interface',
  'general.user_data': 'UserData',
  'general.topology_data': 'TopologyData',
  'general.display_tag': 'DisplayTag',
  'general.modeling_file': 'ModelingFile',
  'general.common_data_file': 'CommonDataFile',
  'snmp.read_community': 'ReadCommunity',
  'snmp.write_community': 'WriteCommunity',
  'snmp.mib_file': 'MibFile',
  'snmp.agent_file': 'AgentFile',
  'snmp.trap_mgr': 'TrapMgr',
  'snmp.snmp_str': 'SnmpStr',
  'snmp.response_delay': 'ResponseDelay',
  'snmp.mtu_size': 'MtuSize',
  'snmp.snmp_port': 'SnmpPort',
  'snmp.security_level': 'SecurityLevel',
  'snmp.user_name': 'UserName',
  'ssh.ssh_user_name': 'SSHUserName',
  'ssh.ssh_password': 'SSHPassword',
  'ssh.ssh_scp_base_dir': 'SSHSCPBaseDir',
  'ssh.ssh_version': 'SSHVersion',
  'ssh.ssh_file': 'SSHFile',
  'soap.soap_http_port': 'SoapHttpPort',
  'soap.soap_https_port': 'SoapHttpsPort',
  'soap.xml_https_type': 'XmlHttpsType',
  'soap.soap_mod_file': 'SoapModFile',
  'soap.soap_content_type': 'SoapContentType',
};

// Reverse: DeviceField enum value → UI field path
const deviceFieldToPath: Record<string, string> = Object.fromEntries(
  Object.entries(fieldPathToDeviceField).map(([path, field]) => [field, path])
);

export const EditFieldsDialog: React.FC<EditFieldsDialogProps> = ({ open, simulators, onClose, onSuccess }) => {
  const isSingle = simulators.length === 1;
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldStates>({});

  // Streaming progress state
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamDone, setStreamDone] = useState(false);
  const [progressItems, setProgressItems] = useState<ProgressItem[]>([]);
  const [streamSummary, setStreamSummary] = useState<{ success: number; failed: number; total: number } | null>(null);

  // File lists state
  const [fileListsLoading, setFileListsLoading] = useState(false);
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

  // Load file lists and current fields when dialog opens
  useEffect(() => {
    if (open && simulators.length > 0) {
      setFields({});
      setFetchError(null);
      setIsStreaming(false);
      setStreamDone(false);
      setProgressItems([]);
      setStreamSummary(null);
      loadFileLists();
      if (simulators.length === 1) {
        fetchCurrentFields();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, simulators]);

  const loadFileLists = async () => {
    setFileListsLoading(true);
    try {
      const [mibRes, agentRes, sshRes, soapRes, modelingRes] = await Promise.all([
        apiClient.get('/sapro-files/mib'),
        apiClient.get('/sapro-files/agent'),
        apiClient.get('/sapro-files/ssh'),
        apiClient.get('/sapro-files/soap'),
        apiClient.get('/sapro-files/modeling'),
      ]);

      const ensureStringArray = (data: any): string[] => {
        if (!data || !data.files || !Array.isArray(data.files)) return [];
        return data.files.filter((f: any) => typeof f === 'string');
      };

      setFileLists({
        mib: ensureStringArray(mibRes.data),
        agent: ensureStringArray(agentRes.data),
        ssh: ensureStringArray(sshRes.data),
        soap: ensureStringArray(soapRes.data),
        modeling: ensureStringArray(modelingRes.data),
      });
    } catch (err) {
      console.error('Failed to load file lists:', err);
      setFileLists({ mib: [], agent: [], ssh: [], soap: [], modeling: [] });
    } finally {
      setFileListsLoading(false);
    }
  };

  const fetchCurrentFields = async () => {
    if (simulators.length === 0) return;
    setIsFetching(true);
    setFetchError(null);
    try {
      const resp = await apiClient.get(`/simulators/${simulators[0].ip_address}/fields`, { timeout: 60000 });
      const rawFields: Record<string, string> = resp.data.fields;

      // Map DeviceField names → UI field paths, all unchecked
      const initialFields: FieldStates = {};
      for (const [deviceFieldName, value] of Object.entries(rawFields)) {
        const path = deviceFieldToPath[deviceFieldName];
        if (path) {
          initialFields[path] = { enabled: false, value };
        }
      }
      setFields(initialFields);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load simulator fields';
      setFetchError(msg);
    } finally {
      setIsFetching(false);
    }
  };

  const handleFieldToggle = (fieldPath: string) => {
    setFields(prev => ({
      ...prev,
      [fieldPath]: {
        enabled: !prev[fieldPath]?.enabled,
        value: prev[fieldPath]?.value || '',
      },
    }));
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

  const handleSubmit = async () => {
    if (simulators.length === 0) return;

    const enabledFields: Record<string, string> = {};
    for (const [path, state] of Object.entries(fields)) {
      if (state.enabled) {
        const deviceField = fieldPathToDeviceField[path];
        if (deviceField) {
          enabledFields[deviceField] = state.value;
        }
      }
    }

    if (Object.keys(enabledFields).length === 0) return;

    const ipsParam = simulators.map(s => s.ip_address).join(',');

    // Initialize progress items — first one starts as "processing"
    const initial: ProgressItem[] = simulators.map((s, i) => ({
      ip: s.ip_address,
      status: i === 0 ? 'processing' : 'pending',
      message: '',
    }));
    setProgressItems(initial);
    setIsStreaming(true);
    setStreamDone(false);
    setStreamSummary(null);

    activityTracker.pauseTracking();
    try {
      const baseURL = apiClient.defaults.baseURL || '';
      const url = `${baseURL}/simulators/${ipsParam}/update-fields/stream`;
      const token = localStorage.getItem('token');

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ fields: enabledFields }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split('\n\n');
        buffer = messages.pop() || '';

        for (const message of messages) {
          if (message.startsWith('data: ')) {
            try {
              const evt = JSON.parse(message.slice(6));
              if (evt.type === 'progress') {
                setProgressItems(prev => {
                  const updated = prev.map(item =>
                    item.ip === evt.ip
                      ? { ...item, status: evt.status as ProgressStatus, message: evt.message }
                      : item
                  );
                  // Mark next pending item as processing
                  const nextIdx = updated.findIndex(item => item.status === 'pending');
                  if (nextIdx !== -1) {
                    updated[nextIdx] = { ...updated[nextIdx], status: 'processing' };
                  }
                  return updated;
                });
              } else if (evt.type === 'complete') {
                setStreamSummary({ success: evt.success_count, failed: evt.failed_count, total: evt.total_count });
                setIsStreaming(false);
                setStreamDone(true);
                reader.releaseLock();
                onSuccess();
                return;
              } else if (evt.type === 'error') {
                reader.releaseLock();
                throw new Error(evt.message);
              }
            } catch (parseErr) {
              console.error('Failed to parse SSE message:', parseErr);
            }
          }
        }
      }

      reader.releaseLock();
      setIsStreaming(false);
      setStreamDone(true);
    } catch (err: any) {
      setIsStreaming(false);
      setStreamDone(false);
      setProgressItems([]);
      alert(err?.message || 'Failed to update fields');
    } finally {
      activityTracker.resumeTracking();
    }
  };

  const hasAnyEnabled = Object.values(fields).some(s => s.enabled);

  // Helper to extract filename from full path
  const extractFilename = (fullPath: string): string => {
    const parts = fullPath.split('/');
    return parts[parts.length - 1] || '';
  };

  const renderField = (label: string, fieldPath: string, helperText?: string) => {
    const state = fields[fieldPath] || { enabled: false, value: '' };
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
          value={state.value}
          onChange={(e) => handleFieldValueChange(fieldPath, e.target.value)}
          helperText={typeof helperText === 'string' ? helperText : undefined}
          sx={{ '& .MuiInputBase-input.Mui-disabled': { backgroundColor: '#f5f5f5' } }}
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
    const state = fields[fieldPath] || { enabled: false, value: '' };
    const files = fileLists[fileType] || [];
    const currentValue = extractFilename(state.value);
    const fileExistsInList = currentValue && files.includes(currentValue);
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
          <TextField
            label={label}
            fullWidth
            size="small"
            value={state.value}
            onChange={(e) => handleFieldValueChange(fieldPath, e.target.value)}
            helperText={`File not found in list. Manual entry: ${state.value}`}
            sx={{ '& .MuiInputBase-input': { backgroundColor: '#FFF3E0' } }}
          />
        ) : (
          <FormControl
            fullWidth
            size="small"
            disabled={!state.enabled || fileListsLoading}
            sx={{ '& .MuiInputBase-root.Mui-disabled': { backgroundColor: '#f5f5f5' } }}
          >
            <InputLabel>{label}</InputLabel>
            <Select
              value={currentValue}
              label={label}
              onChange={(e) => {
                const filename = e.target.value;
                const pathMap: Record<string, string> = {
                  mib: '/opt/sapro/cmf/',
                  agent: '/opt/sapro/var/',
                  ssh: '/opt/sapro/telnet/',
                  soap: '/opt/sapro/xml/',
                  modeling: '/opt/sapro/tcl/',
                };
                handleFieldValueChange(fieldPath, filename ? `${pathMap[fileType]}${filename}` : '');
              }}
            >
              <MenuItem value="">
                <em>{fileListsLoading ? 'Loading...' : 'None'}</em>
              </MenuItem>
              {files.filter(f => typeof f === 'string').map((file) => (
                <MenuItem key={file} value={file}>{file}</MenuItem>
              ))}
            </Select>
            {helperText && <Typography variant="caption" sx={{ mt: 0.5, color: 'text.secondary' }}>{helperText}</Typography>}
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
      slotProps={{ paper: { sx: { margin: '32px', maxHeight: 'calc(100% - 64px)' } } }}
    >
      <DialogTitle>
        {isStreaming
          ? 'Updating Fields...'
          : streamDone
            ? 'Update Complete'
            : isSingle
              ? `Edit Fields: ${simulators[0].ip_address}`
              : `Edit Fields: ${simulators.length} simulators`}
      </DialogTitle>

      <DialogContent sx={{ paddingTop: '24px !important' }}>
        {/* Progress view */}
        {(isStreaming || streamDone) ? (
          <Box>
            {/* Progress bar */}
            {isStreaming && (
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    {progressItems.filter(i => i.status === 'success' || i.status === 'failed').length} / {progressItems.length}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(progressItems.filter(i => i.status === 'success' || i.status === 'failed').length / progressItems.length) * 100}
                />
              </Box>
            )}

            {/* Summary */}
            {streamDone && streamSummary && (
              <Alert
                severity={streamSummary.failed === 0 ? 'success' : streamSummary.success === 0 ? 'error' : 'warning'}
                sx={{ mb: 2 }}
              >
                {streamSummary.failed === 0
                  ? `Successfully updated all ${streamSummary.success} simulator(s)`
                  : `Updated ${streamSummary.success}/${streamSummary.total}, ${streamSummary.failed} failed`}
              </Alert>
            )}

            {/* Per-simulator progress list */}
            <Box sx={{ maxHeight: 350, overflowY: 'auto' }}>
              {progressItems.map(item => (
                <Box
                  key={item.ip}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    py: 1,
                    px: 1,
                    borderBottom: '1px solid #f0f0f0',
                    '&:last-child': { borderBottom: 'none' },
                  }}
                >
                  {item.status === 'processing' && <CircularProgress size={18} />}
                  {item.status === 'success' && <CheckCircleOutlineIcon sx={{ color: 'success.main', fontSize: 20 }} />}
                  {item.status === 'failed' && <ErrorOutlineIcon sx={{ color: 'error.main', fontSize: 20 }} />}
                  {item.status === 'pending' && <Box sx={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid #ddd', flexShrink: 0 }} />}
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', minWidth: 120 }}>{item.ip}</Typography>
                  {item.message && (
                    <Typography
                      variant="caption"
                      color={item.status === 'failed' ? 'error' : 'text.secondary'}
                      sx={{ flex: 1 }}
                    >
                      {item.message}
                    </Typography>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        ) : (
          /* Form view */
          <>
            {isFetching && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            )}

            {fetchError && (
              <Alert severity="error" sx={{ mb: 2 }}>{fetchError}</Alert>
            )}

            {!isFetching && !fetchError && (
              <>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {isSingle
                    ? 'Check fields to update. Current values are shown — change as needed.'
                    : `Check fields to update. The selected values will be applied to all ${simulators.length} simulators.`}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Accordion defaultExpanded>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1" fontWeight="medium">General</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderField('Multi Home', 'general.multi_home')}
                    {renderField('DHCP', 'general.dhcp')}
                    {renderField('Subnet Mask', 'general.subnet_mask')}
                    {renderField('MAC Address', 'general.mac_address')}
                    {renderField('Interface', 'general.interface')}
                    {renderField('User Data', 'general.user_data')}
                    {renderField('Topology Data', 'general.topology_data')}
                    {renderField('Display Tag', 'general.display_tag')}
                    {renderDropdownField('Modeling File', 'general.modeling_file', 'modeling')}
                    {renderField('Common Data File', 'general.common_data_file')}
                  </AccordionDetails>
                </Accordion>

                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1" fontWeight="medium">SNMP</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderField('Read Community', 'snmp.read_community')}
                    {renderField('Write Community', 'snmp.write_community')}
                    {renderDropdownField('MIB File', 'snmp.mib_file', 'mib')}
                    {renderDropdownField('Agent File', 'snmp.agent_file', 'agent')}
                    {renderField('Trap Manager', 'snmp.trap_mgr')}
                    {renderField('SNMP String', 'snmp.snmp_str')}
                    {renderField('Response Delay', 'snmp.response_delay')}
                    {renderField('MTU Size', 'snmp.mtu_size')}
                    {renderField('SNMP Port', 'snmp.snmp_port')}
                    {renderField('Security Level', 'snmp.security_level')}
                    {renderField('User Name', 'snmp.user_name')}
                  </AccordionDetails>
                </Accordion>

                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1" fontWeight="medium">SOAP</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderField('SOAP HTTP Port', 'soap.soap_http_port')}
                    {renderField('SOAP HTTPS Port', 'soap.soap_https_port')}
                    {renderField('XML HTTPS Type', 'soap.xml_https_type')}
                    {renderDropdownField('SOAP Mod File', 'soap.soap_mod_file', 'soap')}
                    {renderField('SOAP Content Type', 'soap.soap_content_type')}
                  </AccordionDetails>
                </Accordion>

                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1" fontWeight="medium">SSH</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderField('SSH User Name', 'ssh.ssh_user_name')}
                    {renderField('SSH Password', 'ssh.ssh_password')}
                    {renderField('SSH SCP Base Dir', 'ssh.ssh_scp_base_dir')}
                    {renderField('SSH Version', 'ssh.ssh_version')}
                    {renderDropdownField('SSH File', 'ssh.ssh_file', 'ssh')}
                  </AccordionDetails>
                </Accordion>
              </>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        {(isStreaming || streamDone) ? (
          <Button
            onClick={() => { setIsStreaming(false); setStreamDone(false); onClose(); }}
            variant="contained"
            disabled={isStreaming}
          >
            {isStreaming ? 'Please wait...' : 'Close'}
          </Button>
        ) : (
          <>
            <Button onClick={onClose} disabled={isLoading}>Cancel</Button>
            <Button
              onClick={handleSubmit}
              variant="contained"
              disabled={isLoading || isFetching || !hasAnyEnabled}
            >
              {isLoading ? <CircularProgress size={20} /> : 'Update Fields'}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default EditFieldsDialog;
