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

const CCManagementPage: React.FC = () => {
    const navigate = useNavigate();

    const [addDialogOpen, setAddDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deviceToDelete, setDeviceToDelete] = useState<string | null>(null);
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
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
    const [currentPhase, setCurrentPhase] = useState<'adding' | 'waiting' | null>(null);
    const [deviceProgress, setDeviceProgress] = useState<{
        current: number;
        total: number;
        ip: string;
        name: string;
        status: 'adding' | 'added' | 'checking' | 'success' | 'failed';
        message: string;
    } | null>(null);

    const currentCC = useCCStore((state) => state.currentCC);
    const devices = useCCStore((state) => state.devices);  // Raw CC devices
    const saproSimulators = useCCStore((state) => state.saproSimulators);  // All Sapro simulators
    const isLoading = useCCStore((state) => state.isLoading);
    const fetchDevices = useCCStore((state) => state.fetchDevices);
    const addDevice = useCCStore((state) => state.addDevice);
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

    const handleAddDeviceSubmit = async (data: CCAddDeviceRequest) => {
        if (!currentCC) return;

        // Check if IP is a range
        const isRange = data.management_ip && data.management_ip.includes('-');

        if (isRange) {
            // Use streaming with status check for ranges
            setIsAdding(true);
            setCurrentDevice(0);
            setTotalDevices(0);
            setDeviceProgress(null);
            setAddDialogOpen(false); // Close dialog immediately for streaming

            try {
                await ccService.addDeviceWithStatusCheck(
                    currentCC,
                    data,
                    (current, total, ip, name, status, message) => {
                        setCurrentDevice(current);
                        setTotalDevices(total);

                        // Detect phase from status
                        if (status === 'adding' || status === 'added') {
                            setCurrentPhase('adding');
                        } else if (status === 'checking' || status === 'success' || status === 'failed') {
                            setCurrentPhase('waiting');
                        }

                        setDeviceProgress({
                            current,
                            total,
                            ip,
                            name,
                            status,
                            message
                        });
                    },
                    (successCount, failedCount, totalCount) => {
                        setIsAdding(false);
                        setDeviceProgress(null);
                        setCurrentPhase(null);
                        if (failedCount === 0) {
                            setSnackbar({
                                open: true,
                                message: `Successfully added all ${successCount} device(s)`,
                                severity: 'success'
                            });
                        } else if (successCount === 0) {
                            setSnackbar({
                                open: true,
                                message: `Failed to add all ${failedCount} device(s)`,
                                severity: 'error'
                            });
                        } else {
                            setSnackbar({
                                open: true,
                                message: `Added ${successCount} device(s), ${failedCount} failed`,
                                severity: 'success'
                            });
                        }
                        // Refresh devices after completion
                        fetchDevices(currentCC);
                    },
                    (error) => {
                        setIsAdding(false);
                        setDeviceProgress(null);
                        setCurrentPhase(null);
                        setSnackbar({
                            open: true,
                            message: `Error: ${error}`,
                            severity: 'error'
                        });
                    }
                );
            } catch (err: any) {
                setIsAdding(false);
                setDeviceProgress(null);
                const msg = err?.response?.data?.detail || err?.message || 'Failed to add devices';
                setSnackbar({open: true, message: msg, severity: 'error'});
            }
        } else {
            // Single IP - use regular addDevice
            try {
                await addDevice(currentCC, data);
                setAddDialogOpen(false);
                setSnackbar({open: true, message: 'Device added successfully', severity: 'success'});
            } catch (err: any) {
                const msg = err?.response?.data?.detail || err?.message || 'Failed to add device';
                setSnackbar({open: true, message: msg, severity: 'error'});
            }
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
                            onClick={() => currentCC && fetchDevices(currentCC, true)}
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
                                {currentPhase === 'adding' ? 'Adding Devices to CyberController...' :
                                    currentPhase === 'waiting' ? 'Waiting for All Devices to be Up...' :
                                        deviceProgress?.status === 'success' ? 'All Devices Ready!' :
                                            deviceProgress?.status === 'failed' ? 'Some Devices Failed' :
                                                'Processing...'}
                            </Typography>

                            {/* Phase-aware counter */}
                            {currentDevice > 0 && (
                                <Box sx={{textAlign: 'center'}}>
                                    <Typography variant="h5" fontWeight="bold" color="primary">
                                        {currentPhase === 'adding' ? 'Adding: ' : currentPhase === 'waiting' ? 'Waiting: ' : ''}
                                        {currentDevice}/{totalDevices}
                                    </Typography>
                                    <Typography variant="caption" color="textSecondary">
                                        {currentPhase === 'adding' && 'Adding devices to CyberController...'}
                                        {currentPhase === 'waiting' && 'Waiting for all devices to be up...'}
                                    </Typography>
                                </Box>
                            )}

                            {/* Current device details */}
                            {deviceProgress && (
                                <Box sx={{textAlign: 'center', mt: 2}}>
                                    <Typography variant="body1" fontWeight="medium">
                                        {deviceProgress.ip} - {deviceProgress.name}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: deviceProgress.status === 'failed' ? 'error.main' :
                                                deviceProgress.status === 'success' ? 'success.main' :
                                                    'text.secondary',
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
