import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar, Alert, TextField } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import Layout from '../components/common/Layout';
import { SimulatorTable } from '../components/simulator/SimulatorTable';
import SimulatorFormDialog from '../components/simulator/SimulatorFormDialog';
import useSimulatorStore from '../store/simulatorStore';
import { Simulator, SimulatorCreate, SimulatorUpdate } from '../types/simulator.types';

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

export const SimulatorsPage: React.FC = () => {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedSimulator, setSelectedSimulator] = useState<Simulator | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [simulatorToDelete, setSimulatorToDelete] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<SnackbarState>({ open: false, message: '', severity: 'success' });
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'ip_address' | 'type' | 'version' | 'status'>('ip_address');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const {
    simulators,
    isLoading,
    fetchSimulators,
    createSimulator,
    updateSimulator,
    deleteSimulator,
  } = useSimulatorStore();

  useEffect(() => {
    fetchSimulators();
  }, []);

  const handleCreate = () => {
    setSelectedSimulator(null);
    setFormOpen(true);
  };

  const handleEdit = (sim: Simulator) => {
    setSelectedSimulator(sim);
    setFormOpen(true);
  };

  const handleDeleteClick = (ip: string) => {
    setSimulatorToDelete(ip);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!simulatorToDelete) return;
    try {
      await deleteSimulator(simulatorToDelete);
      setSnackbar({ open: true, message: 'Simulator deleted', severity: 'success' });
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.message || 'Failed to delete simulator', severity: 'error' });
    } finally {
      setDeleteDialogOpen(false);
      setSimulatorToDelete(null);
    }
  };

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    try {
      if (selectedSimulator) {
        await updateSimulator(selectedSimulator.ip_address, data as SimulatorUpdate);
        setSnackbar({ open: true, message: 'Simulator updated', severity: 'success' });
      } else {
        await createSimulator(data as SimulatorCreate);
        setSnackbar({ open: true, message: 'Simulator created', severity: 'success' });
      }
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.message || 'Operation failed', severity: 'error' });
    } finally {
      setFormOpen(false);
      setSelectedSimulator(null);
    }
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setSelectedSimulator(null);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSimulatorToDelete(null);
  };

  const handleSnackbarClose = (_?: any, reason?: string) => {
    if (reason === 'clickaway') return;
    setSnackbar((s) => ({ ...s, open: false }));
  };

  const handleSort = (column: 'ip_address' | 'type' | 'version' | 'status') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const filteredSimulators = simulators.filter(sim => {
    const search = searchTerm.toLowerCase();
    const ipMatch = sim.ip_address?.toLowerCase().includes(search) || false;
    const typeMatch = sim.type?.toLowerCase().includes(search) || false;
    const versionMatch = sim.version?.toLowerCase().includes(search) || false;
    const mapMatch = sim.map?.toLowerCase().includes(search) || false;
    const statusMatch = sim.status?.toLowerCase().includes(search) || false;
    return ipMatch || typeMatch || versionMatch || mapMatch || statusMatch;
  });

  const sortedSimulators = [...filteredSimulators].sort((a, b) => {
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
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">Simulator Management</Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>Create Simulator</Button>
        </Box>

        <TextField
          placeholder="Search by IP, type, version, map, or status..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          fullWidth
          sx={{ marginBottom: 3 }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ color: '#999', marginRight: 1 }} />
          }}
        />

        <SimulatorTable
          simulators={sortedSimulators}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          isLoading={isLoading}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSort={handleSort}
        />

        <SimulatorFormDialog
          open={formOpen}
          simulator={selectedSimulator}
          onClose={handleFormClose}
          onSubmit={handleFormSubmit}
        />

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <DialogContentText>Are you sure you want to delete this simulator?</DialogContentText>

            {simulatorToDelete !== null && simulators.find(s => s.ip_address === simulatorToDelete) && (
              <Box sx={{ marginTop: 2, padding: 2, background: '#FFF3E0', borderRadius: 1, border: '1px solid #FFB74D' }}>
                <Typography variant="body2" sx={{ fontWeight: 600, marginBottom: 1 }}>Simulator Details:</Typography>
                <Typography variant="body2">IP Address: <strong>{simulators.find(s => s.ip_address === simulatorToDelete)?.ip_address}</strong></Typography>
                <Typography variant="body2">Type: <strong>{simulators.find(s => s.ip_address === simulatorToDelete)?.type || 'Unknown'}</strong></Typography>
                <Typography variant="body2">Version: <strong>{simulators.find(s => s.ip_address === simulatorToDelete)?.version || 'Unknown'}</strong></Typography>
              </Box>
            )}

            <Typography variant="body2" sx={{ marginTop: 2, color: '#d32f2f' }}>
              This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel}>Cancel</Button>
            <Button onClick={handleDeleteConfirm} color="error" variant="contained">Delete</Button>
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

export default SimulatorsPage;
