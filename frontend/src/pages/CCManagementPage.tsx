import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
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
import LogoutIcon from '@mui/icons-material/Logout';
import SearchIcon from '@mui/icons-material/Search';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import Layout from '../components/common/Layout';
import { CCDeviceTable } from '../components/cc/CCDeviceTable';
import { CCAddDeviceDialog } from '../components/cc/CCAddDeviceDialog';
import useCCStore from '../store/ccStore';
import { CCAddDeviceRequest } from '../types/cc.types';

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

  const currentCC = useCCStore((state) => state.currentCC);
  const devices = useCCStore((state) => state.devices);
  const isLoading = useCCStore((state) => state.isLoading);
  const fetchDevices = useCCStore((state) => state.fetchDevices);
  const addDevice = useCCStore((state) => state.addDevice);
  const deleteDevice = useCCStore((state) => state.deleteDevice);
  const logout = useCCStore((state) => state.logout);
  const clearState = useCCStore((state) => state.clearState);

  useEffect(() => {
    if (!currentCC) {
      navigate('/cc/login');
    } else {
      fetchDevices(currentCC);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAddDevice = () => setAddDialogOpen(true);

  const handleAddDeviceSubmit = async (data: CCAddDeviceRequest) => {
    if (!currentCC) return;
    try {
      await addDevice(currentCC, data);
      setAddDialogOpen(false);
      setSnackbar({ open: true, message: 'Device added successfully', severity: 'success' });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to add device';
      setSnackbar({ open: true, message: msg, severity: 'error' });
    }
  };

  const handleAddDialogClose = () => setAddDialogOpen(false);

  const handleDeleteClick = (management_ip: string) => {
    setDeviceToDelete(management_ip);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!currentCC || !deviceToDelete) return;
    try {
      await deleteDevice(currentCC, deviceToDelete);
      setDeleteDialogOpen(false);
      setSnackbar({ open: true, message: 'Device deleted successfully', severity: 'success' });
      setDeviceToDelete(null);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to delete device';
      setSnackbar({ open: true, message: msg, severity: 'error' });
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setDeviceToDelete(null);
  };

  const handleSnackbarClose = (_?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') return;
    setSnackbar((s) => ({ ...s, open: false }));
  };

  const handleLogout = async () => {
    if (!currentCC) return;
    try {
      await logout(currentCC);
      clearState();
      navigate('/cc/login');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Logout failed';
      setSnackbar({ open: true, message: msg, severity: 'error' });
    }
  };

  const handleSort = (column: 'management_ip' | 'name' | 'device_type' | 'status') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const filteredDevices = devices.filter(device => {
    const search = searchTerm.toLowerCase();
    const ipMatch = device.management_ip.toLowerCase().includes(search);
    const nameMatch = device.name?.toLowerCase().includes(search) || false;
    const typeMatch = device.device_type?.toLowerCase().includes(search) || false;
    const statusMatch = device.status?.toLowerCase().includes(search) || false;
    return ipMatch || nameMatch || typeMatch || statusMatch;
  });

  const sortedDevices = [...filteredDevices].sort((a, b) => {
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
      <Box sx={{ p: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4">CyberController Management</Typography>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button startIcon={<LogoutIcon />} variant="outlined" onClick={handleLogout}>
              Logout from CC
            </Button>

            <Button startIcon={<AddIcon />} variant="contained" onClick={handleAddDevice}>
              Add Device
            </Button>
          </Box>
        </Box>

        <Typography variant="body2" sx={{ color: '#666', mb: 2 }}>
          Connected to: {currentCC}
        </Typography>

        <TextField
          placeholder="Search by IP, name, type, or status..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          fullWidth
          sx={{ marginBottom: 3 }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ color: '#999', marginRight: 1 }} />,
          }}
        />

        <CCDeviceTable devices={sortedDevices} onDelete={handleDeleteClick} isLoading={isLoading} sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />

        <CCAddDeviceDialog open={addDialogOpen} onClose={handleAddDialogClose} onSubmit={handleAddDeviceSubmit} />

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete this device from CyberController?
            </DialogContentText>

            {deviceToDelete !== null && devices.find(d => d.management_ip === deviceToDelete) && (
              <Box sx={{ marginTop: 2, padding: 2, background: '#FFF3E0', borderRadius: 1, border: '1px solid #FFB74D' }}>
                <Typography variant="body2" sx={{ fontWeight: 600, marginBottom: 1 }}>Device Details:</Typography>
                <Typography variant="body2">Management IP: <strong>{devices.find(d => d.management_ip === deviceToDelete)?.management_ip}</strong></Typography>
                <Typography variant="body2">Name: <strong>{devices.find(d => d.management_ip === deviceToDelete)?.name || 'Unknown'}</strong></Typography>
                <Typography variant="body2">Type: <strong>{devices.find(d => d.management_ip === deviceToDelete)?.device_type || 'Unknown'}</strong></Typography>
              </Box>
            )}

            <Typography variant="body2" sx={{ marginTop: 2, color: '#d32f2f' }}>
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

        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleSnackbarClose}>
          <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Layout>
  );
};

export default CCManagementPage;
