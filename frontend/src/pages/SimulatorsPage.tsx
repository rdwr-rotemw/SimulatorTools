import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar, Alert } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import Layout from '../components/common/Layout';
import SimulatorTable from '../components/simulator/SimulatorTable';
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

  const {
    simulators,
    isLoading,
    error,
    fetchSimulators,
    createSimulator,
    updateSimulator,
    deleteSimulator,
    clearError,
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

  return (
    <Layout>
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">Simulator Management</Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>Create Simulator</Button>
        </Box>

        <SimulatorTable
          simulators={simulators}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          isLoading={isLoading}
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

