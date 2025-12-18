import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Snackbar,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Paper,
  IconButton,
  Collapse,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  List,
  ListItemText,
  ListItemButton,
  CircularProgress,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import AddIcon from '@mui/icons-material/Add';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import UploadIcon from '@mui/icons-material/Upload';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import DeleteIcon from '@mui/icons-material/Delete';
import LoopIcon from '@mui/icons-material/Loop';
import StopIcon from '@mui/icons-material/Stop';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';

import Layout from '../components/common/Layout';
import useCCStore from '../store/ccStore';
import { SNMPTrapForm } from '../components/snmp/SNMPTrapForm';
import { SNMPTrap, SNMPFormErrors } from '../types/snmp.types';
import { SNMP_FIELD_DEFAULTS } from '../constants/snmp.constants';
import { validateIPAddress, validatePort, validatePositiveInteger, isValidSamplesFormat, mapPcapEnumsToFormValues } from '../utils/snmp.utils';
import { snmpTemplateService } from '../api/services/snmpTemplate.service';
import apiClient from '../api/client';

export const SNMPPage: React.FC = () => {
  const navigate = useNavigate();
  const currentCC = useCCStore((state) => state.currentCC);
  const devicesList = useCCStore((state) => state.devices);
  const managementPorts = useCCStore((state) => state.managementPorts);

  const [selectedSimulator, setSelectedSimulator] = useState<string>('');
  const [selectedDestinationPort, setSelectedDestinationPort] = useState<string>('');
  const [traps, setTraps] = useState<SNMPTrap[]>([{
    attackName: '',
    policy: '',
    ...SNMP_FIELD_DEFAULTS,
  }]);
  const [expandedTraps, setExpandedTraps] = useState<number[]>([0]);
  const [errors, setErrors] = useState<{ [key: number]: SNMPFormErrors }>({});
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({ open: false, message: '', severity: 'success' });

  // Loop functionality state
  const [loopDialogOpen, setLoopDialogOpen] = useState(false);
  const [loopDelay, setLoopDelay] = useState<number>(15); // seconds - default 15s
  const [loopTimeout, setLoopTimeout] = useState<number>(600); // seconds - default 10 minutes, mandatory
  const [isLooping, setIsLooping] = useState(false);
  const loopIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loopTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pcapFileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Dialog / templates state
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [loadDialogOpen, setLoadDialogOpen] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [availableTemplates, setAvailableTemplates] = useState<Array<{ name: string; created_at: string; trap_count: number }>>([]);

  useEffect(() => {
    if (!currentCC) {
      navigate('/cc/login');
    }
  }, [currentCC, navigate]);

  // Cleanup loop on unmount
  useEffect(() => {
    return () => {
      if (loopIntervalRef.current) clearInterval(loopIntervalRef.current);
      if (loopTimeoutRef.current) clearTimeout(loopTimeoutRef.current);
    };
  }, []);

  // When management ports update, pick a sensible default (prefer G2, then G1)
  useEffect(() => {
    if (managementPorts && managementPorts.length > 0) {
      const g2Port = managementPorts.find((p: any) => p.interface === 'G2');
      const g1Port = managementPorts.find((p: any) => p.interface === 'G1');
      const defaultPort = g2Port || g1Port || managementPorts[0];
      if (defaultPort && defaultPort.address) setSelectedDestinationPort(defaultPort.address);
    }
  }, [managementPorts]);

  const addTrap = () => {
    setTraps([...traps, { attackName: '', policy: '', ...SNMP_FIELD_DEFAULTS }]);
    setExpandedTraps([...expandedTraps, traps.length]);
  };

  const handleToggleAllTraps = () => {
    const allExpanded = expandedTraps.length === traps.length;
    if (allExpanded) {
      setExpandedTraps([]);
    } else {
      setExpandedTraps(traps.map((_, i) => i));
    }
  };

  const deleteTrap = (index: number) => {
    if (traps.length === 1) {
      setSnackbar({ open: true, message: 'Must have at least one trap', severity: 'error' });
      return;
    }
    const newTraps = traps.filter((_, i) => i !== index);
    setTraps(newTraps);
    // adjust expanded indices
    setExpandedTraps(expandedTraps.filter(i => i !== index).map(i => (i > index ? i - 1 : i)));
    // shift errors mapping
    const newErrors: { [key: number]: SNMPFormErrors } = {};
    Object.keys(errors).forEach((k) => {
      const ki = parseInt(k, 10);
      if (ki === index) return;
      const newIndex = ki > index ? ki - 1 : ki;
      newErrors[newIndex] = errors[ki];
    });
    setErrors(newErrors);
  };

  const updateTrap = (index: number, updated: SNMPTrap) => {
    const newTraps = [...traps];
    newTraps[index] = updated;
    setTraps(newTraps);
  };

  const toggleTrap = (index: number) => {
    setExpandedTraps(expandedTraps.includes(index)
      ? expandedTraps.filter(i => i !== index)
      : [...expandedTraps, index]
    );
  };

  const handleDownload = () => {
    const data = JSON.stringify({ traps }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `snmp-traps-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setSnackbar({ open: true, message: 'Traps downloaded', severity: 'success' });
  };

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string);
        if (data.traps && Array.isArray(data.traps)) {
          setTraps(data.traps);
          setExpandedTraps(data.traps.map((_: any, i: number) => i));
          setSnackbar({ open: true, message: 'Traps imported successfully', severity: 'success' });
        } else {
          setSnackbar({ open: true, message: 'JSON does not contain traps array', severity: 'error' });
        }
      } catch (error) {
        setSnackbar({ open: true, message: 'Invalid JSON file', severity: 'error' });
      }
    };
    reader.readAsText(file);
    // reset input so same file can be re-picked
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handlePcapUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate extension
    if (!file.name.toLowerCase().endsWith('.pcap')) {
      setUploadError('Please select a .pcap file');
      if (pcapFileInputRef.current) pcapFileInputRef.current.value = '';
      return;
    }

    setUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await apiClient.post('/reporter/snmp/import-from-pcap', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const data = response.data || {};

      // 1) If API indicates failure, throw its error message first
      if (typeof data.success !== 'undefined' && data.success === false) {
        throw new Error(data.error || 'Server reported an error while parsing PCAP');
      }

      // 2) Ensure parsed traps exist in the expected location: data.data.traps
      const parsedTraps = data?.data?.traps;
      if (!parsedTraps || !Array.isArray(parsedTraps) || parsedTraps.length === 0) {
        throw new Error('No traps were parsed from the PCAP file');
      }

      // 3) Success - replace traps and show notifications
      const normalizedTraps = mapPcapEnumsToFormValues(parsedTraps);
      setTraps(normalizedTraps.length > 0 ? normalizedTraps : parsedTraps);
      setExpandedTraps(parsedTraps.map((_: any, i: number) => i));
      setSnackbar({ open: true, message: `Imported ${parsedTraps.length} trap(s) from PCAP`, severity: 'success' });

      if (data.warning) {
        setSnackbar({ open: true, message: data.warning, severity: 'info' });
      }
    } catch (err: any) {
      // Error precedence: API error message (response.data.error) -> thrown Error message -> default
      const msg = err?.response?.data?.error || err?.message || 'Failed to upload PCAP';
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (pcapFileInputRef.current) pcapFileInputRef.current.value = '';
    }
  };

  const handleSave = () => {
    setSaveDialogOpen(true);
    setTemplateName('');
  };

  const handleSaveConfirm = async () => {
    if (!templateName.trim()) {
      setSnackbar({ open: true, message: 'Template name is required', severity: 'error' });
      return;
    }

    try {
      await snmpTemplateService.saveTemplate(currentCC!, templateName, traps);
      setSnackbar({ open: true, message: `Template "${templateName}" saved successfully`, severity: 'success' });
      setSaveDialogOpen(false);
      setTemplateName('');
    } catch (error: any) {
      setSnackbar({ open: true, message: error?.response?.data?.detail || 'Failed to save template', severity: 'error' });
    }
  };

  const handleLoadClick = async () => {
    try {
      const templates = await snmpTemplateService.listTemplates(currentCC!);
      setAvailableTemplates(templates);
      setLoadDialogOpen(true);
    } catch (error: any) {
      setSnackbar({ open: true, message: 'Failed to load templates', severity: 'error' });
    }
  };

  const handleLoadTemplate = async (name: string) => {
    try {
      const template = await snmpTemplateService.getTemplate(currentCC!, name);
      setTraps(template.traps);
      setExpandedTraps(template.traps.map((_: any, i: number) => i));
      setSnackbar({ open: true, message: `Template "${name}" loaded`, severity: 'success' });
      setLoadDialogOpen(false);
    } catch (error: any) {
      setSnackbar({ open: true, message: 'Failed to load template', severity: 'error' });
    }
  };

  const handleSend = async () => {
    if (!selectedSimulator) {
      setSnackbar({ open: true, message: 'Please select a simulator', severity: 'error' });
      return;
    }

    if (!selectedDestinationPort) {
      setSnackbar({ open: true, message: 'Please select a destination port', severity: 'error' });
      return;
    }

    if (!validateAll()) {
      setSnackbar({ open: true, message: 'Please fix validation errors', severity: 'error' });
      return;
    }

    try {
      setSnackbar({ open: true, message: 'Sending traps...', severity: 'info' });
      await snmpTemplateService.sendTraps(selectedDestinationPort, selectedSimulator, traps);
      setSnackbar({ open: true, message: `Successfully sent ${traps.length} trap(s)`, severity: 'success' });
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to send traps';
      setSnackbar({ open: true, message: errorMsg, severity: 'error' });
    }
  };

  const handleCloseSnackbar = (_?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') return;
    setSnackbar((s) => ({ ...s, open: false }));
  };

  const validateAll = (): boolean => {
    const newErrors: { [key: number]: SNMPFormErrors } = {};
    traps.forEach((t, idx) => {
      const e: SNMPFormErrors = {};
      if (!t.attackName || !t.attackName.trim()) e.attackName = 'Attack Name is required';
      if (!t.policy || !t.policy.trim()) e.policy = 'Policy is required';
      if (t.srcIp && !validateIPAddress(t.srcIp)) e.srcIp = 'Invalid IP address';
      if (t.dstIp && !validateIPAddress(t.dstIp)) e.dstIp = 'Invalid IP address';
      if (t.srcPort && !validatePort(t.srcPort)) e.srcPort = 'Invalid port (0-65535)';
      if (t.dstPort && !validatePort(t.dstPort)) e.dstPort = 'Invalid port (0-65535)';
      if (t.physicalPort && !validatePositiveInteger(t.physicalPort)) e.physicalPort = 'Must be a positive integer';
      if (t.packetCount && !validatePositiveInteger(t.packetCount)) e.packetCount = 'Must be a positive integer';
      if (t.packetBandwidth && !validatePositiveInteger(t.packetBandwidth)) e.packetBandwidth = 'Must be a positive integer';
      if (t.samples && !isValidSamplesFormat(t.samples)) e.samples = 'Invalid format (use 0-0-0)';
      if (Object.keys(e).length > 0) newErrors[idx] = e;
    });
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const sendTrapsOnce = async () => {
    try {
      await snmpTemplateService.sendTraps(selectedDestinationPort, selectedSimulator, traps);
      return true;
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to send traps';
      setSnackbar({ open: true, message: errorMsg, severity: 'error' });
      return false;
    }
  };

  const handleStartLoop = () => {
    if (!selectedSimulator) {
      setSnackbar({ open: true, message: 'Please select a simulator', severity: 'error' });
      return;
    }

    if (!selectedDestinationPort) {
      setSnackbar({ open: true, message: 'Please select a destination port', severity: 'error' });
      return;
    }

    if (!validateAll()) {
      setSnackbar({ open: true, message: 'Please fix validation errors', severity: 'error' });
      return;
    }

    if (loopDelay < 1) {
      setSnackbar({ open: true, message: 'Loop delay must be at least 1 second', severity: 'error' });
      return;
    }

    if (loopTimeout < 1) {
      setSnackbar({ open: true, message: 'Timeout must be at least 1 second', severity: 'error' });
      return;
    }

    setLoopDialogOpen(false);
    setIsLooping(true);

    let trapsSentCount = 0;
    const startTime = Date.now();

    // Send first trap immediately
    sendTrapsOnce().then(success => {
      if (success) {
        trapsSentCount++;
        setSnackbar({ open: true, message: `Loop started - Sent batch #${trapsSentCount}`, severity: 'info' });
      }
    });

    // Set up interval for subsequent sends (convert seconds to milliseconds)
    loopIntervalRef.current = setInterval(async () => {
      const success = await sendTrapsOnce();
      if (success) {
        trapsSentCount++;
        setSnackbar({ open: true, message: `Loop running - Sent batch #${trapsSentCount}`, severity: 'info' });
      }
    }, loopDelay * 1000);

    // Set up timeout - always runs since timeout is mandatory
    loopTimeoutRef.current = setTimeout(() => {
      handleStopLoop();
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
      setSnackbar({
        open: true,
        message: `Loop stopped after ${elapsedSeconds}s - Sent ${trapsSentCount} batch(es)`,
        severity: 'success'
      });
    }, loopTimeout * 1000);
  };

  const handleStopLoop = () => {
    if (loopIntervalRef.current) {
      clearInterval(loopIntervalRef.current);
      loopIntervalRef.current = null;
    }
    if (loopTimeoutRef.current) {
      clearTimeout(loopTimeoutRef.current);
      loopTimeoutRef.current = null;
    }
    setIsLooping(false);
  };

  const handleOpenLoopDialog = () => {
    setLoopDialogOpen(true);
  };

  return (
    <Layout>
      <Box sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
        {/* Fixed Header */}
        <Box sx={{ padding: 3, borderBottom: '1px solid #E0E0E0' }}>
          <Typography variant="h4" sx={{ marginBottom: 1 }}>SNMP Trap Sender</Typography>
          <Typography variant="body2" sx={{ color: '#666', marginBottom: 2 }}>
            Connected to CyberController at {currentCC}
          </Typography>

          <FormControl fullWidth>
            <InputLabel>Target Simulator</InputLabel>
            <Select
              value={selectedSimulator}
              onChange={(e) => setSelectedSimulator(e.target.value as string)}
              label="Target Simulator"
            >
              {devicesList.map((device) => (
                <MenuItem key={device.management_ip} value={device.management_ip}>
                  {device.name || device.management_ip} ({device.management_ip})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {/* Destination Port selector populated from CC management ports */}
          <FormControl fullWidth sx={{ marginTop: 2 }}>
            <InputLabel>Destination Port</InputLabel>
            <Select
              value={selectedDestinationPort}
              onChange={(e) => setSelectedDestinationPort(e.target.value as string)}
              label="Destination Port"
            >
              {managementPorts.map((port) => (
                <MenuItem key={port.interface} value={port.address}>
                  {port.interface}: {port.address}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* Scrollable Trap List */}
        <Box sx={{ flex: 1, overflow: 'auto', padding: 3 }}>
          {traps.map((t, index) => (
            <Paper key={index} sx={{ marginBottom: 2, padding: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                <Typography variant="h6">Trap {index + 1}</Typography>
                <Box>
                  <IconButton onClick={() => toggleTrap(index)}>
                    {expandedTraps.includes(index) ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                  <IconButton onClick={() => deleteTrap(index)} color="error">
                    <DeleteIcon />
                  </IconButton>
                </Box>
              </Box>

              <Collapse in={expandedTraps.includes(index)}>
                <SNMPTrapForm
                  trap={t}
                  onChange={(updatedTrap) => updateTrap(index, updatedTrap)}
                  errors={errors[index] || {}}
                />
              </Collapse>
            </Paper>
          ))}
        </Box>

        {/* Fixed Footer with Actions */}
        <Box sx={{ padding: 3, borderTop: '1px solid #E0E0E0', display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={addTrap}>
            Add Trap
          </Button>

          <Button
            variant="outlined"
            startIcon={expandedTraps.length === traps.length ? <UnfoldLessIcon /> : <UnfoldMoreIcon />}
            onClick={handleToggleAllTraps}
          >
            {expandedTraps.length === traps.length ? 'Collapse All' : 'Expand All'}
          </Button>

          <Button variant="outlined" startIcon={<SaveIcon />} onClick={handleSave}>
            Save Template
          </Button>

          <Button variant="outlined" startIcon={<DownloadIcon />} onClick={handleDownload}>
            Download JSON
          </Button>

          <Button variant="outlined" startIcon={<UploadIcon />} onClick={handleLoadClick}>
            Load Template
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={handleImport}
          />

          <Button
            variant="outlined"
            startIcon={uploading ? <CircularProgress size={18} color="inherit" /> : <CloudUploadIcon />}
            onClick={() => pcapFileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? 'Importing PCAP...' : 'Import from PCAP'}
          </Button>
          <input
            ref={pcapFileInputRef}
            type="file"
            accept=".pcap"
            style={{ display: 'none' }}
            onChange={handlePcapUpload}
          />

          {uploadError && (
            <Box sx={{ width: '100%' }}>
              <Alert severity="error" onClose={() => setUploadError(null)} sx={{ mt: 1 }}>
                {uploadError}
              </Alert>
            </Box>
          )}

          <Box sx={{ flex: 1 }} />

          <Button
            variant="contained"
            color="primary"
            startIcon={<SendIcon />}
            onClick={handleSend}
            disabled={!selectedSimulator || !selectedDestinationPort || isLooping}
          >
            Send Traps ({traps.length})
          </Button>

          {!isLooping ? (
            <Button
              variant="contained"
              color="secondary"
              startIcon={<LoopIcon />}
              onClick={handleOpenLoopDialog}
              disabled={!selectedSimulator || !selectedDestinationPort}
            >
              Send Loop
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              startIcon={<StopIcon />}
              onClick={handleStopLoop}
            >
              Stop Loop
            </Button>
          )}
        </Box>
      </Box>

      {/* Loop Configuration Dialog */}
      <Dialog open={loopDialogOpen} onClose={() => setLoopDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Configure Send Loop</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Loop Delay (seconds)"
            type="number"
            fullWidth
            value={loopDelay}
            onChange={(e) => setLoopDelay(Math.floor(parseInt(e.target.value) || 0))}
            helperText="Time between sending traps (minimum 1 second)"
            inputProps={{ min: 1, step: 1 }}
          />
          <TextField
            margin="dense"
            label="Timeout (seconds)"
            type="number"
            fullWidth
            required
            value={loopTimeout}
            onChange={(e) => setLoopTimeout(Math.floor(parseInt(e.target.value) || 0))}
            helperText="Loop will automatically stop after this duration (required, minimum 1 second)"
            inputProps={{ min: 1, step: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLoopDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleStartLoop} variant="contained" color="secondary">
            Start Loop
          </Button>
        </DialogActions>
      </Dialog>

      {/* Save Template Dialog */}
      <Dialog open={saveDialogOpen} onClose={() => setSaveDialogOpen(false)}>
        <DialogTitle>Save Template</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Template Name"
            fullWidth
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSaveConfirm()}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveConfirm} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>

      {/* Load Template Dialog */}
      <Dialog open={loadDialogOpen} onClose={() => setLoadDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Load Template</DialogTitle>
        <DialogContent>
          {availableTemplates.length === 0 ? (
            <Typography variant="body2" sx={{ padding: 2, textAlign: 'center', color: '#666' }}>
              No saved templates found
            </Typography>
          ) : (
            <List>
              {availableTemplates.map((template) => (
                <ListItemButton key={template.name} onClick={() => handleLoadTemplate(template.name)}>
                  <ListItemText
                    primary={template.name}
                    secondary={`${template.trap_count} trap(s) • Created: ${new Date(template.created_at).toLocaleString()}`}
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLoadDialogOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Layout>
  );
};
