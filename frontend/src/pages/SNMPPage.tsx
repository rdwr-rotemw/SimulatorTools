import React, {useState, useEffect, useRef} from 'react';
import {useNavigate} from 'react-router-dom';
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
    Autocomplete,
    Checkbox,
    Chip,
    Tooltip,
    FormControlLabel,
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
import useLoopStore from '../store/useLoopStore';
import useFormStore from '../store/useFormStore';
import useAuthStore from '../store/authStore';
import {SNMPTrapForm} from '../components/snmp/SNMPTrapForm';
import AttackIdConfigDialog from '../components/snmp/AttackIdConfigDialog';
import {SNMPTrap, SNMPFormErrors} from '../types/snmp.types';
import {SNMP_FIELD_DEFAULTS} from '../constants/snmp.constants';
import {
    validateIPAddress,
    validatePort,
    validatePositiveInteger,
    isValidSamplesFormat,
    mapPcapEnumsToFormValues
} from '../utils/snmp.utils';
import {snmpTemplateService} from '../api/services/snmpTemplate.service';
import apiClient from '../api/client';

export const SNMPPage: React.FC = () => {
    const navigate = useNavigate();
    const currentCC = useCCStore((state) => state.currentCC);
    const devices = useCCStore((state) => state.devices);
    const saproSimulators = useCCStore((state) => state.saproSimulators);

    // Filter devices: only show those that exist in Sapro
    const saproIPs = new Set(saproSimulators.map(sim => sim.ip_address));
    const devicesList = devices.filter(device => saproIPs.has(device.management_ip));

    const managementPorts = useCCStore((state) => state.managementPorts);
    const user = useAuthStore((state) => state.user);

    const [selectedSimulators, setSelectedSimulators] = useState<string[]>([]);
    const [selectedDestinationPort, setSelectedDestinationPort] = useState<string>('');
    const [traps, setTraps] = useState<SNMPTrap[]>([{
        attackName: '',
        policy: '',
        ...SNMP_FIELD_DEFAULTS,
    }]);
    const [expandedTraps, setExpandedTraps] = useState<number[]>([0]);
    const [errors, setErrors] = useState<{ [key: number]: SNMPFormErrors }>({});
    const [snackbar, setSnackbar] = useState<{
        open: boolean;
        message: string;
        severity: 'success' | 'error' | 'info'
    }>({open: false, message: '', severity: 'success'});

    // Sending progress state
    const [isSending, setIsSending] = useState(false);
    const [currentTrap, setCurrentTrap] = useState(0);
    const [totalTraps, setTotalTraps] = useState(0);

    // Loop functionality state
    const [loopDialogOpen, setLoopDialogOpen] = useState(false);
    const [loopDelay, setLoopDelay] = useState<number>(15); // seconds - default 15s
    const [loopTimeout, setLoopTimeout] = useState<number>(600); // seconds - default 10 minutes, mandatory
    const [regenerateAttackId, setRegenerateAttackId] = useState<boolean>(false); // New: regenerate attack-ID each iteration
    const isLooping = useLoopStore((state) => state.snmp.isLooping);
    const loopIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const loopTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Attack-ID configuration dialog state
    const [attackIdDialogOpen, setAttackIdDialogOpen] = useState(false);
    const [pendingAction, setPendingAction] = useState<'send' | 'loop' | null>(null);
    const [configuredAttackIds, setConfiguredAttackIds] = useState<Record<string, string[]> | null>(null);

    // Ref to hold current send function to prevent stale closures
    const sendTrapsOnceRef = useRef<() => Promise<boolean>>(async () => false);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const pcapFileInputRef = useRef<HTMLInputElement>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

    // Dialog / templates state
    const [saveDialogOpen, setSaveDialogOpen] = useState(false);
    const [loadDialogOpen, setLoadDialogOpen] = useState(false);
    const [templateName, setTemplateName] = useState('');
    const [availableTemplates, setAvailableTemplates] = useState<Array<{
        name: string;
        created_at: string;
        trap_count: number
    }>>([]);

    useEffect(() => {
        if (!currentCC) {
            navigate('/cc/login');
        }
    }, [currentCC, navigate]);

    // Set current session and restore form state on mount
    useEffect(() => {
        // Step 1: Set current session (auto-clears if session changed)
        if (currentCC && user) {
            useFormStore.getState().setCurrentSession(currentCC, user.username);
        }

        // Step 2: Try to restore form state (will be null if session was cleared)
        const formState = useFormStore.getState().getSnmpFormState();

        // Only restore if we have saved form state AND current traps is still the default empty trap
        const hasDefaultTrap = traps.length === 1 &&
            !traps[0].attackName &&
            !traps[0].policy;

        if (formState.traps && formState.traps.length > 0 && hasDefaultTrap) {
            setTraps(formState.traps);
            setExpandedTraps(formState.expandedTraps);
            setSnackbar({
                open: true,
                message: `Form restored from previous session (${formState.traps.length} trap(s))`,
                severity: 'info'
            });
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Restore loop on mount if it was running
    useEffect(() => {
        const loopState = useLoopStore.getState().getSnmpLoopState();

        if (loopState.isLooping && loopState.startTime) {
            // Check if loop hasn't expired
            const remaining = useLoopStore.getState().getRemainingTime('snmp');

            if (remaining > 0) {
                // Restore state to local
                setSelectedSimulators(loopState.simulator);
                setSelectedDestinationPort(loopState.destinationPort);
                setLoopDelay(loopState.loopDelay);
                setLoopTimeout(loopState.loopTimeout);

                // Show restoration message
                setSnackbar({
                    open: true,
                    message: `Loop resumed - ${remaining} seconds remaining, ${loopState.batchesSent} batch(es) sent`,
                    severity: 'info'
                });

                // Recreate interval for remaining sends
                loopIntervalRef.current = setInterval(async () => {
                    const success = await sendTrapsOnceRef.current();
                    if (success) {
                        useLoopStore.getState().incrementSnmpBatches();
                        const currentBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                        setSnackbar({
                            open: true,
                            message: `Loop running - Sent batch #${currentBatches}`,
                            severity: 'info'
                        });
                    }
                }, loopState.loopDelay * 1000);

                // Recreate timeout for remaining duration
                loopTimeoutRef.current = setTimeout(() => {
                    handleStopLoop();
                    const elapsed = useLoopStore.getState().getElapsedTime('snmp');
                    const finalBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                    setSnackbar({
                        open: true,
                        message: `Loop stopped after ${elapsed}s - Sent ${finalBatches} batch(es)`,
                        severity: 'success'
                    });
                }, remaining * 1000);
            } else {
                // Loop expired, clear it
                useLoopStore.getState().clearSnmpLoop();
            }
        }

        // Cleanup on unmount - DO NOT stop loop, just clear local refs
        return () => {
            // DO NOT clear intervals - loop should persist
            // Store state is preserved automatically in localStorage
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        setTraps([...traps, {attackName: '', policy: '', ...SNMP_FIELD_DEFAULTS}]);
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

    // Generate a random attack-ID
    const generateRandomAttackId = (): string => {
        const prefix = Math.floor(Math.random() * 9000) + 100; // 100-9999
        const suffix = Math.floor(Math.random() * 9000000000) + 1000000000; // 10 digits
        return `${prefix}-${suffix}`;
    };

    const deleteTrap = (index: number) => {
        if (traps.length === 1) {
            setSnackbar({open: true, message: 'Must have at least one trap', severity: 'error'});
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
        const data = JSON.stringify({traps}, null, 2);
        const blob = new Blob([data], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `snmp-traps-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        setSnackbar({open: true, message: 'Traps downloaded', severity: 'success'});
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
                    // Clear form store since we're loading new data
                    useFormStore.getState().clearSnmpFormState();
                    setSnackbar({open: true, message: 'Traps imported successfully', severity: 'success'});
                } else {
                    setSnackbar({open: true, message: 'JSON does not contain traps array', severity: 'error'});
                }
            } catch (error) {
                setSnackbar({open: true, message: 'Invalid JSON file', severity: 'error'});
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
                headers: {'Content-Type': 'multipart/form-data'},
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
            // Clear form store since we're loading new data
            useFormStore.getState().clearSnmpFormState();
            setSnackbar({open: true, message: `Imported ${parsedTraps.length} trap(s) from PCAP`, severity: 'success'});

            if (data.warning) {
                setSnackbar({open: true, message: data.warning, severity: 'info'});
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
            setSnackbar({open: true, message: 'Template name is required', severity: 'error'});
            return;
        }

        try {
            await snmpTemplateService.saveTemplate(currentCC!, templateName, traps);
            setSnackbar({open: true, message: `Template "${templateName}" saved successfully`, severity: 'success'});
            setSaveDialogOpen(false);
            setTemplateName('');
        } catch (error: any) {
            setSnackbar({
                open: true,
                message: error?.response?.data?.detail || 'Failed to save template',
                severity: 'error'
            });
        }
    };

    const handleLoadClick = async () => {
        try {
            const templates = await snmpTemplateService.listTemplates(currentCC!);
            setAvailableTemplates(templates);
            setLoadDialogOpen(true);
        } catch (error: any) {
            setSnackbar({open: true, message: 'Failed to load templates', severity: 'error'});
        }
    };

    const handleLoadTemplate = async (name: string) => {
        try {
            const template = await snmpTemplateService.getTemplate(currentCC!, name);
            setTraps(template.traps);
            setExpandedTraps(template.traps.map((_: any, i: number) => i));
            // Clear form store since we're loading a template
            useFormStore.getState().clearSnmpFormState();
            setSnackbar({open: true, message: `Template "${name}" loaded`, severity: 'success'});
            setLoadDialogOpen(false);
        } catch (error: any) {
            setSnackbar({open: true, message: 'Failed to load template', severity: 'error'});
        }
    };

    const handleSend = async () => {
        if (selectedSimulators.length === 0) {
            setSnackbar({open: true, message: 'Please select at least one simulator', severity: 'error'});
            return;
        }

        if (!selectedDestinationPort) {
            setSnackbar({open: true, message: 'Please select a destination port', severity: 'error'});
            return;
        }

        if (selectedSimulators.some(sim => !sim)) {
            setSnackbar({open: true, message: 'One or more selected simulators do not have a map configured', severity: 'error'});
            return;
        }

        if (!validateAll()) {
            setSnackbar({open: true, message: 'Please fix validation errors', severity: 'error'});
            return;
        }

        // If multiple simulators selected, show attack-ID configuration dialog
        if (selectedSimulators.length > 1) {
            setPendingAction('send');
            setAttackIdDialogOpen(true);
            return;
        }

        // Before calling service
        setIsSending(true);
        setCurrentTrap(0);
        setTotalTraps(traps.length);

        try {
            setSnackbar({open: true, message: 'Sending traps...', severity: 'info'});
            await snmpTemplateService.sendTrapsWithProgress(
                selectedDestinationPort,
                selectedSimulators,
                traps,
                (current, total, trapName, status) => {
                    setCurrentTrap(current);
                    setTotalTraps(total);
                },
                (successCount, failedCount, totalCount) => {
                    if (failedCount === 0) {
                        setSnackbar({
                            open: true,
                            message: `Successfully sent all ${successCount} trap(s)`,
                            severity: 'success'
                        });
                    } else {
                        setSnackbar({
                            open: true,
                            message: `Partially successful: ${successCount} succeeded, ${failedCount} failed`,
                            severity: 'error'
                        });
                    }
                },
                (error) => {
                    setSnackbar({open: true, message: error, severity: 'error'});
                }
            );
        } catch (error: any) {
            // Error already handled in onError callback
        } finally {
            // Finally block
            setIsSending(false);
            setCurrentTrap(0);
            setTotalTraps(0);
        }
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
        if (selectedSimulators.length === 0) {
            setSnackbar({open: true, message: 'No simulators selected', severity: 'error'});
            return false;
        }

        if (selectedSimulators.some(sim => !sim)) {
            setSnackbar({open: true, message: 'One or more selected simulators do not have a map configured', severity: 'error'});
            return false;
        }

        try {
            await snmpTemplateService.sendTraps(selectedDestinationPort, selectedSimulators, traps);
            return true;
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || error.message || 'Failed to send traps';
            setSnackbar({open: true, message: errorMsg, severity: 'error'});
            return false;
        }
    };

    // Update ref whenever dependencies change to prevent stale closures
    useEffect(() => {
        sendTrapsOnceRef.current = sendTrapsOnce;
    }, [selectedDestinationPort, selectedSimulators, traps]); // eslint-disable-line react-hooks/exhaustive-deps

    // Auto-save form state to localStorage on every change
    useEffect(() => {
        // Save whenever traps or expandedTraps changes
        // This keeps localStorage in sync with current form state
        useFormStore.getState().setSnmpFormState(traps, expandedTraps);
    }, [traps, expandedTraps]);

    const handleStartLoop = () => {
        // Validation for loop parameters only (other validations done in handleOpenLoopDialog)
        if (loopDelay < 1) {
            setSnackbar({open: true, message: 'Loop delay must be at least 1 second', severity: 'error'});
            return;
        }

        if (loopTimeout < 1) {
            setSnackbar({open: true, message: 'Timeout must be at least 1 second', severity: 'error'});
            return;
        }

        setLoopDialogOpen(false);

        const startTime = Date.now();

        // Save to store BEFORE creating interval
        useLoopStore.getState().setSnmpLoopState({
            isLooping: true,
            loopDelay: loopDelay,
            loopTimeout: loopTimeout,
            startTime: startTime,
            batchesSent: 0,
            simulator: selectedSimulators,
            destinationPort: selectedDestinationPort,
        });

        // Check if we have configured attack-IDs (multi-simulator case)
        if (configuredAttackIds && selectedSimulators.length > 1) {
            // Create a wrapper function that sends with modified attack-IDs
            const sendWithModifiedIds = async () => {
                try {
                    for (const simulatorIp of selectedSimulators) {
                        const modifiedTraps = traps.map((trap, index) => {
                            // If regenerateAttackId is enabled, generate new random attack-ID each iteration
                            const attackId = regenerateAttackId
                                ? generateRandomAttackId()
                                : configuredAttackIds[simulatorIp][index];

                            return {
                                ...trap,
                                attackId: attackId
                            };
                        });

                        await snmpTemplateService.sendTraps(
                            selectedDestinationPort,
                            [simulatorIp],
                            modifiedTraps
                        );
                    }
                    return true;
                } catch (error: any) {
                    const errorMsg = error.response?.data?.detail || error.message || 'Failed to send traps';
                    setSnackbar({open: true, message: errorMsg, severity: 'error'});
                    return false;
                }
            };

            // Send first batch immediately
            sendWithModifiedIds().then(success => {
                if (success) {
                    useLoopStore.getState().incrementSnmpBatches();
                    const currentBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                    setSnackbar({open: true, message: `Loop started - Sent batch #${currentBatches}`, severity: 'info'});
                }
            });

            // Set up interval for subsequent sends
            loopIntervalRef.current = setInterval(async () => {
                const success = await sendWithModifiedIds();
                if (success) {
                    useLoopStore.getState().incrementSnmpBatches();
                    const currentBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                    setSnackbar({open: true, message: `Loop running - Sent batch #${currentBatches}`, severity: 'info'});
                }
            }, loopDelay * 1000);

            // Set up timeout
            loopTimeoutRef.current = setTimeout(() => {
                handleStopLoop();
                const elapsedSeconds = useLoopStore.getState().getElapsedTime('snmp');
                const finalBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                setSnackbar({
                    open: true,
                    message: `Loop stopped after ${elapsedSeconds}s - Sent ${finalBatches} batch(es)`,
                    severity: 'success'
                });
            }, loopTimeout * 1000);

            // Clear configured attack-IDs and pending action
            setConfiguredAttackIds(null);
            setPendingAction(null);
        } else {
            // Single simulator: use normal flow

            // Create send function that handles regenerate attack-ID if enabled
            const sendWithPossibleRegeneration = async () => {
                if (regenerateAttackId) {
                    // Generate new attack-IDs for each trap
                    const trapsWithNewIds = traps.map(trap => ({
                        ...trap,
                        attackId: generateRandomAttackId()
                    }));

                    try {
                        await snmpTemplateService.sendTraps(
                            selectedDestinationPort,
                            selectedSimulators,
                            trapsWithNewIds
                        );
                        return true;
                    } catch (error: any) {
                        const errorMsg = error.response?.data?.detail || error.message || 'Failed to send traps';
                        setSnackbar({open: true, message: errorMsg, severity: 'error'});
                        return false;
                    }
                } else {
                    // Use normal sendTrapsOnce
                    return await sendTrapsOnceRef.current();
                }
            };

            // Send first trap immediately
            sendWithPossibleRegeneration().then(success => {
                if (success) {
                    useLoopStore.getState().incrementSnmpBatches();
                    const currentBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                    setSnackbar({open: true, message: `Loop started - Sent batch #${currentBatches}`, severity: 'info'});
                }
            });

            // Set up interval for subsequent sends (convert seconds to milliseconds)
            loopIntervalRef.current = setInterval(async () => {
                const success = await sendWithPossibleRegeneration();
                if (success) {
                    useLoopStore.getState().incrementSnmpBatches();
                    const currentBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                    setSnackbar({open: true, message: `Loop running - Sent batch #${currentBatches}`, severity: 'info'});
                }
            }, loopDelay * 1000);

            // Set up timeout - always runs since timeout is mandatory
            loopTimeoutRef.current = setTimeout(() => {
                handleStopLoop();
                const elapsedSeconds = useLoopStore.getState().getElapsedTime('snmp');
                const finalBatches = useLoopStore.getState().getSnmpLoopState().batchesSent;
                setSnackbar({
                    open: true,
                    message: `Loop stopped after ${elapsedSeconds}s - Sent ${finalBatches} batch(es)`,
                    severity: 'success'
                });
            }, loopTimeout * 1000);
        }
    };

    const handleAttackIdConfirm = async (attackIdConfig: Record<string, string[]>) => {
        setAttackIdDialogOpen(false);

        if (pendingAction === 'send') {
            // Create modified traps with attack-IDs for each simulator
            // For now, we'll send to each simulator sequentially with modified attack-IDs
            setIsSending(true);
            setCurrentTrap(0);
            setTotalTraps(traps.length * selectedSimulators.length);

            try {
                let successCount = 0;
                let failedCount = 0;

                for (const simulatorIp of selectedSimulators) {
                    const modifiedTraps = traps.map((trap, index) => ({
                        ...trap,
                        attackId: attackIdConfig[simulatorIp][index]
                    }));

                    try {
                        await snmpTemplateService.sendTrapsWithProgress(
                            selectedDestinationPort,
                            [simulatorIp],
                            modifiedTraps,
                            (current, total, trapName, status) => {
                                setCurrentTrap(successCount + failedCount + current);
                            },
                            (simSuccessCount, simFailedCount, totalCount) => {
                                successCount += simSuccessCount;
                                failedCount += simFailedCount;
                            },
                            (error) => {
                                // Error for this simulator
                                failedCount += modifiedTraps.length;
                            }
                        );
                    } catch (error) {
                        failedCount += modifiedTraps.length;
                    }
                }

                if (failedCount === 0) {
                    setSnackbar({
                        open: true,
                        message: `Successfully sent all ${successCount} trap(s) to ${selectedSimulators.length} simulator(s)`,
                        severity: 'success'
                    });
                } else {
                    setSnackbar({
                        open: true,
                        message: `Partially successful: ${successCount} succeeded, ${failedCount} failed`,
                        severity: 'error'
                    });
                }
            } catch (error: any) {
                setSnackbar({
                    open: true,
                    message: error.message || 'Failed to send traps',
                    severity: 'error'
                });
            } finally {
                setIsSending(false);
                setCurrentTrap(0);
                setTotalTraps(0);
            }
            setPendingAction(null);
        } else if (pendingAction === 'loop') {
            // Save the configured attack-IDs and open loop dialog
            setConfiguredAttackIds(attackIdConfig);
            setLoopDialogOpen(true);
            // Don't reset pendingAction yet - we need it in handleStartLoop
        }
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

        // Update store to mark loop as stopped (keep startTime for reference)
        useLoopStore.getState().setSnmpLoopState({
            isLooping: false,
        });
    };

    const handleOpenLoopDialog = () => {
        // Check validations first
        if (selectedSimulators.length === 0) {
            setSnackbar({open: true, message: 'Please select at least one simulator', severity: 'error'});
            return;
        }

        if (!selectedDestinationPort) {
            setSnackbar({open: true, message: 'Please select a destination port', severity: 'error'});
            return;
        }

        if (selectedSimulators.some(sim => !sim)) {
            setSnackbar({open: true, message: 'One or more selected simulators do not have a map configured', severity: 'error'});
            return;
        }

        if (!validateAll()) {
            setSnackbar({open: true, message: 'Please fix validation errors', severity: 'error'});
            return;
        }

        // If multiple simulators, show attack-ID dialog first
        if (selectedSimulators.length > 1) {
            setPendingAction('loop');
            setAttackIdDialogOpen(true);
            return;
        }

        // Single simulator: open loop dialog directly
        setLoopDialogOpen(true);
    };

    return (
        <Layout>
            <Box sx={{height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column'}}>
                {/* Fixed Header */}
                <Box sx={{padding: 3, borderBottom: '1px solid #E0E0E0'}}>
                    <Typography variant="h4" sx={{marginBottom: 1}}>SNMP Trap Sender</Typography>
                    <Typography variant="body2" sx={{color: '#666', marginBottom: 2}}>
                        Connected to CyberController at {currentCC}
                    </Typography>

                    <FormControl fullWidth>
                        <InputLabel id="target-simulator-label">Target Simulator</InputLabel>
                        <Select
                            labelId="target-simulator-label"
                            multiple
                            value={selectedSimulators}
                            onChange={(e) => {
                                const value = e.target.value;
                                const newValue = typeof value === 'string' ? value.split(',') : value;

                                // Check if the special "__SELECT_ALL__" marker is present (from Select All button)
                                if (newValue.includes('__SELECT_ALL__')) {
                                    // Select All was clicked - ignore this onChange and let onClick handle it
                                    return;
                                }

                                // Normal selection change
                                setSelectedSimulators(newValue);
                            }}
                            label="Target Simulator"
                            renderValue={(selected) => (
                                <Box sx={{
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: 0.5,
                                    maxWidth: 'calc(100% - 40px)', // Leave space for dropdown arrow (Select has no clear button)
                                    overflow: 'hidden'
                                }}>
                                    <Chip
                                        label={`${(selected as string[]).length} simulator(s) selected`}
                                        size="small"
                                        sx={{
                                            backgroundColor: 'primary.main',
                                            color: 'white',
                                            maxWidth: '100%',
                                            '& .MuiChip-label': {
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                            }
                                        }}
                                    />
                                </Box>
                            )}
                        >
                            {/* Select All / Deselect All Option */}
                            <MenuItem
                                value="__SELECT_ALL__"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    e.preventDefault();
                                    if (selectedSimulators.length === devicesList.length) {
                                        setSelectedSimulators([]);
                                    } else {
                                        setSelectedSimulators(devicesList.map(d => d.management_ip));
                                    }
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.stopPropagation();
                                        e.preventDefault();
                                        if (selectedSimulators.length === devicesList.length) {
                                            setSelectedSimulators([]);
                                        } else {
                                            setSelectedSimulators(devicesList.map(d => d.management_ip));
                                        }
                                    }
                                }}
                                sx={{ fontWeight: 'bold', borderBottom: '1px solid #e0e0e0' }}
                            >
                                <ListItemText
                                    primary={selectedSimulators.length === devicesList.length ? 'Deselect All' : 'Select All'}
                                />
                            </MenuItem>

                            {/* Device Options */}
                            {devicesList.map((device) => (
                                <MenuItem key={device.management_ip} value={device.management_ip}>
                                    <Checkbox
                                        checked={selectedSimulators.includes(device.management_ip)}
                                        sx={{ marginRight: 1 }}
                                    />
                                    <ListItemText
                                        primary={`${device.name || device.management_ip} (${device.management_ip})`}
                                        secondary={device.map ? `Map: ${device.map}` : undefined}
                                    />
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    {/* Destination Port selector populated from CC management ports */}
                    <FormControl fullWidth sx={{marginTop: 2}}>
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
                <Box sx={{flex: 1, overflow: 'auto', padding: 3}}>
                    {traps.map((t, index) => (
                        <Paper key={index} sx={{marginBottom: 2, padding: 2}}>
                            <Box sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                marginBottom: 2
                            }}>
                                <Typography variant="h6">Trap {index + 1}</Typography>
                                <Box>
                                    <IconButton onClick={() => toggleTrap(index)}>
                                        {expandedTraps.includes(index) ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                                    </IconButton>
                                    <IconButton onClick={() => deleteTrap(index)} color="error">
                                        <DeleteIcon/>
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
                <Box sx={{padding: 3, borderTop: '1px solid #E0E0E0', display: 'flex', gap: 2, flexWrap: 'wrap'}}>
                    <Button variant="outlined" startIcon={<AddIcon/>} onClick={addTrap}>
                        Add Trap
                    </Button>

                    <Button
                        variant="outlined"
                        startIcon={expandedTraps.length === traps.length ? <UnfoldLessIcon/> : <UnfoldMoreIcon/>}
                        onClick={handleToggleAllTraps}
                    >
                        {expandedTraps.length === traps.length ? 'Collapse All' : 'Expand All'}
                    </Button>

                    <Button variant="outlined" startIcon={<SaveIcon/>} onClick={handleSave}>
                        Save Template
                    </Button>

                    <Button variant="outlined" startIcon={<DownloadIcon/>} onClick={handleDownload}>
                        Download JSON
                    </Button>

                    <Button
                        variant="outlined"
                        startIcon={<UploadIcon/>}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        Import JSON
                    </Button>

                    <Button variant="outlined" startIcon={<UploadIcon/>} onClick={handleLoadClick}>
                        Load Template
                    </Button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".json"
                        style={{display: 'none'}}
                        onChange={handleImport}
                    />

                    <Button
                        variant="outlined"
                        startIcon={uploading ? <CircularProgress size={18} color="inherit"/> : <CloudUploadIcon/>}
                        onClick={() => pcapFileInputRef.current?.click()}
                        disabled={uploading}
                    >
                        {uploading ? 'Importing PCAP...' : 'Import from PCAP'}
                    </Button>
                    <input
                        ref={pcapFileInputRef}
                        type="file"
                        accept=".pcap"
                        style={{display: 'none'}}
                        onChange={handlePcapUpload}
                    />

                    {uploadError && (
                        <Box sx={{width: '100%'}}>
                            <Alert severity="error" onClose={() => setUploadError(null)} sx={{mt: 1}}>
                                {uploadError}
                            </Alert>
                        </Box>
                    )}

                    <Box sx={{flex: 1}}/>

                    <Button
                        variant="contained"
                        color="primary"
                        startIcon={<SendIcon/>}
                        onClick={handleSend}
                        disabled={isLooping || isSending}
                    >
                        {isSending ? 'Sending...' : `Send Traps (${traps.length})`}
                    </Button>

                    {!isLooping ? (
                        <Button
                            variant="contained"
                            color="secondary"
                            startIcon={<LoopIcon/>}
                            onClick={handleOpenLoopDialog}
                            disabled={isSending}
                        >
                            Send Loop
                        </Button>
                    ) : (
                        <Button
                            variant="contained"
                            color="error"
                            startIcon={<StopIcon/>}
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
                        inputProps={{min: 1, step: 1}}
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
                        inputProps={{min: 1, step: 1}}
                    />

                    <Tooltip
                        title="When enabled, a new random Attack-ID will be generated for each trap on every iteration of the loop. This ensures unique Attack-IDs are sent to CyberController with each batch, which can be useful for testing or avoiding duplicate attack detection."
                        arrow
                        placement="top"
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={regenerateAttackId}
                                    onChange={(e) => setRegenerateAttackId(e.target.checked)}
                                    color="primary"
                                />
                            }
                            label="Regenerate Attack-ID Each Iteration"
                            sx={{ marginTop: 2 }}
                        />
                    </Tooltip>

                    <Alert severity="info" sx={{ marginTop: 2 }}>
                        Note: Logging out will automatically stop the loop.
                    </Alert>
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
                        <Typography variant="body2" sx={{padding: 2, textAlign: 'center', color: '#666'}}>
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

            {/* Sending Progress Dialog */}
            <Dialog
                open={isSending}
                maxWidth="sm"
                fullWidth
                disableEscapeKeyDown
            >
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                        <CircularProgress size={60} />
                        <Typography variant="h6">
                            Sending Traps...
                        </Typography>
                        {currentTrap > 0 && (
                            <Typography variant="h5" fontWeight="bold" color="primary">
                                {currentTrap}/{totalTraps}
                            </Typography>
                        )}
                        <Typography variant="body2" color="textSecondary">
                            This may take several minutes with pause delays. Please wait...
                        </Typography>
                    </Box>
                </DialogContent>
            </Dialog>

            {/* Attack-ID Configuration Dialog */}
            <AttackIdConfigDialog
                open={attackIdDialogOpen}
                onClose={() => {
                    setAttackIdDialogOpen(false);
                    setPendingAction(null);
                }}
                simulators={selectedSimulators}
                traps={traps}
                onConfirm={handleAttackIdConfirm}
            />

            <Snackbar
                open={snackbar.open}
                autoHideDuration={3000}
                onClose={() => setSnackbar((s) => ({...s, open: false}))}
                anchorOrigin={{vertical: 'top', horizontal: 'center'}}
            >
                <Alert severity={snackbar.severity} sx={{width: '100%'}}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Layout>
    );
};
