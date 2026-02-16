import React, {useEffect, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {
    Box,
    Typography,
    Button,
    CircularProgress,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    Snackbar,
    Alert,
    TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import Layout from '../components/common/Layout';
import {CCDeviceTable} from '../components/cc/CCDeviceTable';
import {CCAddDeviceDialog} from '../components/cc/CCAddDeviceDialog';
import useCCStore from '../store/ccStore';
import {CCAddDeviceRequest} from '../types/cc.types';
import {ccService} from '../api/services/cc.service';

import {CCDeviceDriverDialog} from '../components/cc/CCDeviceDriverDialog';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import {deviceDriverService} from '../api/services/deviceDriver.service';

const CCManagementPage: React.FC = () => {
    const navigate = useNavigate();

    const [addDialogOpen, setAddDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deviceToDelete, setDeviceToDelete] = useState<string | null>(null);
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
        open: false,
        message: '',
        severity: 'success',
    });
    const [searchTerm, setSearchTerm] = useState('');
    const [sortBy, setSortBy] = useState<'management_ip' | 'name' | 'device_type' | 'status'>('management_ip');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
    const [deviceDriverDialogOpen, setDeviceDriverDialogOpen] = useState(false);

    // Progress dialog state
    const [isAdding, setIsAdding] = useState(false);
    const [currentDevice, setCurrentDevice] = useState(0);
    const [totalDevices, setTotalDevices] = useState(0);
    const [currentPhase, setCurrentPhase] = useState<'drivers' | 'adding' | 'validating' | null>(null);
    const [deviceProgress, setDeviceProgress] = useState<{
        current: number;
        total: number;
        ip: string;
        name: string;
        success: boolean;
        message: string;
    } | null>(null);

    const currentCC = useCCStore((state) => state.currentCC);
    const devices = useCCStore((state) => state.devices);  // Raw CC devices
    const saproSimulators = useCCStore((state) => state.saproSimulators);  // All Sapro simulators
    const isLoading = useCCStore((state) => state.isLoading);
    const fetchDevices = useCCStore((state) => state.fetchDevices);
    const fetchSaproSimulators = useCCStore((state) => state.fetchSaproSimulators);
    const deleteDevice = useCCStore((state) => state.deleteDevice);

    // Filter CC devices to only show those that exist in Sapro
    const filteredDevices = devices.filter(device => {
        return saproSimulators.some(sim => sim.ip_address === device.management_ip);
    });

    // Enrich filtered devices with Sapro data (version, map)
    const enrichedDevices = filteredDevices.map(device => {
        const saproSim = saproSimulators.find(sim => sim.ip_address === device.management_ip);
        return {
            ...device,
            version: saproSim?.version || device.version,
            map: saproSim?.map || device.map,
        };
    });

    useEffect(() => {
        if (!currentCC) {
            navigate('/cc/login');
        } else {
            fetchDevices(currentCC);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);


    const handleAddDevice = () => setAddDialogOpen(true);

    const handleDeviceDriverClick = () => setDeviceDriverDialogOpen(true);

    // Helper to parse IP range and extract all IPs
    const parseIPRange = (managementIP: string): string[] => {
        const trimmedValue = managementIP.trim();

        // Check if it's a range
        if (trimmedValue.includes('-')) {
            const [startIP, endIP] = trimmedValue.split('-').map(s => s.trim());

            // Generate all IPs in range
            const parseIP = (ip: string): number[] => ip.split('.').map(Number);
            const start = parseIP(startIP);
            const end = parseIP(endIP);

            const ips: string[] = [];
            const current = [...start];

            while (true) {
                ips.push(current.join('.'));
                if (current.every((val, idx) => val === end[idx])) break;

                for (let i = 3; i >= 0; i--) {
                    if (current[i] < 255) {
                        current[i]++;
                        break;
                    } else {
                        current[i] = 0;
                    }
                }

                if (ips.length > 254) break; // Safety
            }

            return ips;
        } else {
            // Single IP
            return [trimmedValue];
        }
    };

    const handleAddDeviceSubmit = async (data: CCAddDeviceRequest, autoInstallDriver: boolean) => {
        if (!currentCC) return;

        setAddDialogOpen(false); // Close dialog immediately
        setIsAdding(true);
        setCurrentDevice(0);
        setTotalDevices(0);
        setDeviceProgress(null);

        let addSuccessCount = 0;
        let validateSuccessCount = 0;
        let validateFailedCount = 0;

        try {
            // PHASE 1: Add devices
            setCurrentPhase('adding');
            setCurrentDevice(0);
            setTotalDevices(0);
            setDeviceProgress(null);

            await ccService.addDevicesBatch(
                currentCC,
                data,
                (current, total, ip, name, success, message) => {
                    setCurrentDevice(current);
                    setTotalDevices(total);
                    setDeviceProgress({
                        current,
                        total,
                        ip,
                        name,
                        success,
                        message
                    });
                },
                (successCount, _failedCount, totalCount) => {
                    addSuccessCount = successCount;
                },
                (error) => {
                    throw new Error(error);
                }
            );

            // PHASE 2: Install drivers (if enabled)
            if (autoInstallDriver) {
                setCurrentPhase('drivers');

                try {
                    // 1. Extract IP addresses from management_ip field
                    const ipAddresses = parseIPRange(data.management_ip);

                    // 2. Get unique device versions from saproSimulators for these IPs
                    const uniqueVersions = new Map<string, { device_type: string; device_version: string }>();

                    ipAddresses.forEach(ip => {
                        const simulator = saproSimulators.find(sim => sim.ip_address === ip);
                        if (simulator && simulator.type && simulator.version) {
                            const key = `${simulator.type}-${simulator.version}`;
                            if (!uniqueVersions.has(key)) {
                                uniqueVersions.set(key, {
                                    device_type: simulator.type,
                                    device_version: simulator.version
                                });
                            }
                        }
                    });

                    // 3. Get available drivers and match to versions
                    if (uniqueVersions.size > 0) {
                        const allDrivers = await deviceDriverService.listDrivers(currentCC);
                        const matchedDriverFilenames: string[] = [];

                        uniqueVersions.forEach(({ device_type, device_version }) => {
                            const matchedDriver = allDrivers.find(
                                driver => driver.device_type === device_type && driver.device_version === device_version
                            );
                            if (matchedDriver) {
                                matchedDriverFilenames.push(matchedDriver.filename);
                            }
                        });

                        // 4. Deploy matched drivers if any
                        if (matchedDriverFilenames.length > 0) {
                            // Update progress to show driver installation
                            setCurrentDevice(0);
                            setTotalDevices(matchedDriverFilenames.length);
                            setDeviceProgress({
                                current: 0,
                                total: matchedDriverFilenames.length,
                                ip: '',
                                name: `Installing ${matchedDriverFilenames.length} driver(s)...`,
                                success: true,
                                message: 'Installing device drivers...'
                            });

                            const deployResult = await deviceDriverService.deployDrivers(currentCC, matchedDriverFilenames);

                            setCurrentDevice(deployResult.total);
                            setDeviceProgress({
                                current: deployResult.succeeded,
                                total: deployResult.total,
                                ip: '',
                                name: `Installed ${deployResult.succeeded}/${deployResult.total} driver(s)`,
                                success: deployResult.failed === 0,
                                message: deployResult.failed === 0 ? 'All drivers installed successfully' : `${deployResult.failed} driver(s) failed`
                            });

                            if (deployResult.failed > 0) {
                                setSnackbar({
                                    open: true,
                                    message: `Driver installation: ${deployResult.succeeded}/${deployResult.total} succeeded`,
                                    severity: 'warning'
                                });
                            }
                        }
                    }
                } catch (err: any) {
                    // Driver installation failed - show error but continue with validation
                    const msg = err?.response?.data?.detail || err?.message || 'Driver installation failed';
                    setSnackbar({
                        open: true,
                        message: `${msg}. Continuing with validation...`,
                        severity: 'warning'
                    });
                }
            }

            // PHASE 3: Validate devices
            setCurrentPhase('validating');
            setCurrentDevice(0);
            setTotalDevices(0);
            setDeviceProgress(null);

            await ccService.validateDevicesBatch(
                currentCC,
                data,
                (current, total, ip, name, success, message) => {
                    setCurrentDevice(current);
                    setTotalDevices(total);
                    setDeviceProgress({
                        current,
                        total,
                        ip,
                        name,
                        success,
                        message
                    });
                },
                (successCount, failedCount, totalCount) => {
                    validateSuccessCount = successCount;
                    validateFailedCount = failedCount;
                },
                (error) => {
                    throw new Error(error);
                }
            );

            // All phases complete - keep dialog open for 2 seconds while refreshing
            setDeviceProgress({
                current: validateSuccessCount,
                total: validateSuccessCount + validateFailedCount,
                ip: '',
                name: 'Refreshing device list...',
                success: true,
                message: 'Waiting for CyberController to update...'
            });

            // Refresh devices and Sapro simulators (force refresh like manual button)
            fetchSaproSimulators(true);
            fetchDevices(currentCC, true);

            // Wait 2 seconds before closing dialog
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Close dialog
            setIsAdding(false);
            setDeviceProgress(null);
            setCurrentPhase(null);

            // Show final summary
            if (validateFailedCount === 0) {
                setSnackbar({
                    open: true,
                    message: `Successfully added and validated all ${validateSuccessCount} device(s)`,
                    severity: 'success'
                });
            } else if (validateSuccessCount === 0) {
                setSnackbar({
                    open: true,
                    message: `All ${validateFailedCount} device(s) failed validation`,
                    severity: 'error'
                });
            } else {
                setSnackbar({
                    open: true,
                    message: `Added ${addSuccessCount} device(s), ${validateSuccessCount} validated successfully, ${validateFailedCount} failed`,
                    severity: 'warning'
                });
            }

        } catch (err: any) {
            setIsAdding(false);
            setDeviceProgress(null);
            setCurrentPhase(null);
            const msg = err?.response?.data?.detail || err?.message || 'Operation failed';
            setSnackbar({open: true, message: msg, severity: 'error'});
        }
    };

    const handleAddDialogClose = () => setAddDialogOpen(false);

    const handleDeleteClick = (device_id: string) => {
        setDeviceToDelete(device_id);
        setDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!currentCC || !deviceToDelete) return;
        try {
            await deleteDevice(currentCC, deviceToDelete);
            setDeleteDialogOpen(false);
            setSnackbar({open: true, message: 'Device deleted successfully', severity: 'success'});
            setDeviceToDelete(null);
        } catch (err: any) {
            const msg = err?.response?.data?.detail || err?.message || 'Failed to delete device';
            setSnackbar({open: true, message: msg, severity: 'error'});
        }
    };

    const handleDeleteCancel = () => {
        setDeleteDialogOpen(false);
        setDeviceToDelete(null);
    };

    const handleSnackbarClose = (_?: React.SyntheticEvent | Event, reason?: string) => {
        if (reason === 'clickaway') return;
        setSnackbar((s) => ({...s, open: false}));
    };

    const handleSort = (column: 'management_ip' | 'name' | 'device_type' | 'status') => {
        if (sortBy === column) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setSortBy(column);
            setSortOrder('asc');
        }
    };

    // Apply search filter to enriched devices
    const filteredSearchDevices = enrichedDevices.filter(device => {
        const search = searchTerm.toLowerCase();
        const ipMatch = device.management_ip.toLowerCase().includes(search);
        const nameMatch = device.name?.toLowerCase().includes(search) || false;
        const typeMatch = device.device_type?.toLowerCase().includes(search) || false;
        const statusMatch = device.status?.toLowerCase().includes(search) || false;
        return ipMatch || nameMatch || typeMatch || statusMatch;
    });

    const sortedDevices = [...filteredSearchDevices].sort((a, b) => {
        let aValue: any = a[sortBy];
        let bValue: any = b[sortBy];

        // Handle null/undefined values
        if (aValue == null) aValue = '';
        if (bValue == null) bValue = '';

        if (typeof aValue === 'string') aValue = aValue.toLowerCase();
        if (typeof bValue === 'string') bValue = bValue.toLowerCase();

        if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
        return 0;
    });

    return (
        <Layout>
            <Box sx={{p: 4}}>
                <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3}}>
                    <Typography variant="h4">CyberController Management</Typography>

                    <Box sx={{display: 'flex', gap: 2}}>
                        <Button
                            startIcon={<RefreshIcon/>}
                            variant="outlined"
                            onClick={() => {
                                if (currentCC) {
                                    fetchSaproSimulators(true);
                                    fetchDevices(currentCC, true);
                                }
                            }}
                            disabled={isLoading}
                        >
                            Refresh
                        </Button>


                        <Button
                            startIcon={<CloudUploadIcon/>}
                            variant="outlined"
                            onClick={handleDeviceDriverClick}
                        >
                            Upload Device Drivers
                        </Button>

                        <Button startIcon={<AddIcon/>} variant="contained" onClick={handleAddDevice}>
                            Add Device
                        </Button>
                    </Box>
                </Box>

                <Typography variant="body2" sx={{color: '#666', mb: 2}}>
                    Connected to: {currentCC}
                </Typography>

                <TextField
                    placeholder="Search by IP, name, type, or status..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    fullWidth
                    sx={{marginBottom: 3}}
                    InputProps={{
                        startAdornment: <SearchIcon sx={{color: '#999', marginRight: 1}}/>,
                    }}
                />

                <CCDeviceTable devices={sortedDevices} onDelete={handleDeleteClick} isLoading={isLoading}
                               sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort}/>

                <CCAddDeviceDialog
                    open={addDialogOpen}
                    onClose={handleAddDialogClose}
                    onSubmit={handleAddDeviceSubmit}
                    ccIp={currentCC || ''}
                />

                <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
                    <DialogTitle>Confirm Delete</DialogTitle>
                    <DialogContent>
                        <DialogContentText>
                            Are you sure you want to delete this device from CyberController?
                        </DialogContentText>

                        {deviceToDelete !== null && devices.find(d => d.device_id === deviceToDelete) && (
                            <Box sx={{
                                marginTop: 2,
                                padding: 2,
                                background: '#FFF3E0',
                                borderRadius: 1,
                                border: '1px solid #FFB74D'
                            }}>
                                <Typography variant="body2" sx={{fontWeight: 600, marginBottom: 1}}>Device
                                    Details:</Typography>
                                <Typography variant="body2">Management
                                    IP: <strong>{devices.find(d => d.device_id === deviceToDelete)?.management_ip}</strong></Typography>
                                <Typography
                                    variant="body2">Name: <strong>{devices.find(d => d.device_id === deviceToDelete)?.name || 'Unknown'}</strong></Typography>
                                <Typography
                                    variant="body2">Type: <strong>{devices.find(d => d.device_id === deviceToDelete)?.device_type || 'Unknown'}</strong></Typography>
                            </Box>
                        )}

                        <Typography variant="body2" sx={{marginTop: 2, color: '#d32f2f'}}>
                            This action will remove the device from CyberController and cannot be undone.
                        </Typography>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={handleDeleteCancel}>Cancel</Button>
                        <Button onClick={handleDeleteConfirm} color="error">
                            Delete
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Device Addition Progress Dialog */}
                <Dialog
                    open={isAdding}
                    maxWidth="sm"
                    fullWidth
                    disableEscapeKeyDown
                >
                    <DialogContent>
                        <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3}}>
                            <CircularProgress size={60}/>
                            <Typography variant="h6">
                                {currentPhase === 'drivers' ? 'Installing Device Drivers...' :
                                    currentPhase === 'adding' ? 'Adding Devices to CyberController...' :
                                        currentPhase === 'validating' ? 'Validating Devices Are Up...' :
                                            'Processing...'}
                            </Typography>

                            {/* Phase-aware counter */}
                            {currentDevice > 0 && totalDevices > 0 && (
                                <Box sx={{textAlign: 'center'}}>
                                    <Typography variant="h5" fontWeight="bold" color="primary">
                                        {currentPhase === 'drivers' ? 'Drivers: ' :
                                            currentPhase === 'adding' ? 'Adding: ' :
                                                currentPhase === 'validating' ? 'Validating: ' : ''}
                                        {currentDevice}/{totalDevices}
                                    </Typography>
                                    <Typography variant="caption" color="textSecondary">
                                        {currentPhase === 'drivers' && 'Installing device drivers...'}
                                        {currentPhase === 'adding' && 'Adding devices to CyberController...'}
                                        {currentPhase === 'validating' && 'Validating devices are up...'}
                                    </Typography>
                                </Box>
                            )}

                            {/* Current device details */}
                            {deviceProgress && (
                                <Box sx={{textAlign: 'center', mt: 2}}>
                                    <Typography variant="body1" fontWeight="medium">
                                        {deviceProgress.ip && `${deviceProgress.ip} - `}{deviceProgress.name}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: !deviceProgress.success ? 'error.main' :
                                                'success.main',
                                            mt: 1
                                        }}
                                    >
                                        {deviceProgress.message}
                                    </Typography>
                                </Box>
                            )}
                        </Box>
                    </DialogContent>
                </Dialog>

                <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleSnackbarClose}>
                    <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{width: '100%'}}>
                        {snackbar.message}
                    </Alert>
                </Snackbar>
            </Box>

            <CCDeviceDriverDialog
                open={deviceDriverDialogOpen}
                onClose={() => setDeviceDriverDialogOpen(false)}
                ccIp={currentCC || ''}
                devices={enrichedDevices}  // ✅ RIGHT - has version from SAPRO
            />
        </Layout>
    );
};

export default CCManagementPage;
